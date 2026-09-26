from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator

from .supply import (
    SUPPLY_EVALUATOR,
    evaluate_supply_utility,
    is_supply_scenario,
    supply_constraint_violations,
    validate_supply_configuration,
    validate_supply_terms,
)


class ScenarioError(ValueError):
    pass


class ScenarioNotFoundError(LookupError):
    pass


SUPPORTED_COMPARISON_OPERATORS = {"eq", "ne", "lt", "lte", "gt", "gte", "in"}
SUPPORTED_LOGICAL_OPERATORS = {"and", "or", "not"}
SUPPORTED_VALUE_FUNCTIONS = {"linear", "piecewise_linear", "categorical"}
OPENING_KINDS = ("opening_offer", "opening_position")
CONVERSATION_STYLES = {"pragmatic", "analytical", "relationship_focused"}
MAX_EXCHANGE_CANDIDATES = 512
_DIALOGUE_REASON_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_DIALOGUE_REASON_NON_QUALITATIVE = re.compile(
    r"\b(?:RUB|RUR|USD|EUR|GBP|CNY|euro[sz]?|dollars?|рубл[а-я]*|евро|доллар[а-я]*|"
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|"
    r"percent|weeks?|months?|years?|january|february|march|april|may|june|july|august|"
    r"september|october|november|december|ноль|один|одна|одно|два|две|три|четыре|пять|"
    r"шесть|семь|восемь|девять|десять|сто|тысяч[а-я]*|миллион[а-я]*|процент[а-я]*|"
    r"недел[а-я]*|месяц[а-я]*|год|года|лет|январ[а-я]*|феврал[а-я]*|март[а-я]*|"
    r"апрел[а-я]*|ма[йяею]|июн[а-я]*|июл[а-я]*|август[а-я]*|сентябр[а-я]*|"
    r"октябр[а-я]*|ноябр[а-я]*|декабр[а-я]*)\b",
    re.IGNORECASE,
)
_DIALOGUE_REASON_UNSAFE_STRUCTURE = re.compile(
    r"[\[\]{}<>`*_#\\]|https?://|\bBearer\s+\S+|"
    r"(?<![A-Za-z0-9_])(?:nt_|sk[-_])[A-Za-z0-9._~+/=-]{8,}|"
    r"\b(?:system|assistant|user|player|npc|оппонент|игрок|система|ассистент)\s*:",
    re.IGNORECASE,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def authored_opening(scenario: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Return the one explicitly authored opening without filling omitted terms."""

    openings: list[tuple[str, str, dict[str, Any]]] = []
    for role, data in scenario["roles"].items():
        role_opening_kinds = [kind for kind in OPENING_KINDS if kind in data]
        if len(role_opening_kinds) > 1:
            raise ScenarioError(
                f"Role {role!r} must not define both opening_offer and opening_position"
            )
        if role_opening_kinds:
            kind = role_opening_kinds[0]
            terms = data[kind]
            if not isinstance(terms, dict):
                raise ScenarioError(f"{kind} for role {role!r} must be an object")
            openings.append((role, kind, terms))
    if len(openings) != 1:
        raise ScenarioError(
            "Exactly one role must define one opening_offer or opening_position object"
        )
    return openings[0]


@dataclass(frozen=True, slots=True)
class CompiledScenario:
    source: dict[str, Any]
    source_path: Path
    content_digest: str
    compiled_digest: str
    compiler_version: str

    @property
    def id(self) -> str:
        return str(self.source["id"])

    @property
    def version(self) -> int:
        return int(self.source["version"])

    def public_metadata(self) -> dict[str, Any]:
        scenario = self.source
        opening_offer_role, opening_kind, _opening_terms = authored_opening(scenario)
        metadata = {
            "id": scenario["id"],
            "version": scenario["version"],
            "title": scenario["title"],
            "language": scenario["language"],
            "currency": scenario["currency"],
            "max_rounds": scenario["protocol"]["max_rounds"],
            "roles": [
                {"role": role, "company": data["company"]}
                for role, data in scenario["roles"].items()
            ],
            "opening_offer_role": opening_offer_role,
            "opening_kind": opening_kind,
            "negotiable_terms": list(scenario["terms"]["definitions"]),
            "scenario_content_digest": self.content_digest,
            "scenario_compiler_version": self.compiler_version,
            "compiled_scenario_digest": self.compiled_digest,
        }
        if is_supply_scenario(scenario):
            metadata["negotiation_contract_version"] = scenario["negotiation_contract"]
        return metadata


def _load_document(path: Path) -> dict[str, Any]:
    try:
        if path.suffix.lower() == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        else:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ScenarioError(f"Cannot read scenario {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ScenarioError(f"Scenario document must be an object: {path}")
    return value


def _validate_expression(expression: Any, path: str) -> None:
    if not isinstance(expression, dict):
        raise ScenarioError(f"{path} must be an expression object")
    if set(expression) == {"term"} and isinstance(expression["term"], str):
        return
    if set(expression) == {"const"}:
        return
    operator = expression.get("op")
    if operator in SUPPORTED_COMPARISON_OPERATORS:
        if set(expression) != {"op", "left", "right"}:
            raise ScenarioError(f"{path} binary expression requires op, left, and right")
        _validate_expression(expression["left"], f"{path}.left")
        _validate_expression(expression["right"], f"{path}.right")
        return
    if operator == "not":
        if set(expression) != {"op", "arg"}:
            raise ScenarioError(f"{path} not expression requires op and arg")
        _validate_expression(expression["arg"], f"{path}.arg")
        return
    if operator in {"and", "or"}:
        args = expression.get("args")
        if set(expression) != {"op", "args"} or not isinstance(args, list) or not args:
            raise ScenarioError(f"{path} {operator} expression requires a non-empty args list")
        for index, item in enumerate(args):
            _validate_expression(item, f"{path}.args[{index}]")
        return
    raise ScenarioError(f"{path} uses unsupported expression operator: {operator!r}")


def _validate_value_function(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ScenarioError(f"{path} must be an object")
    function_type = value.get("type")
    if function_type not in SUPPORTED_VALUE_FUNCTIONS:
        raise ScenarioError(f"{path} uses unsupported value function: {function_type!r}")
    weight = value.get("weight")
    if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0:
        raise ScenarioError(f"{path}.weight must be a non-negative number")
    if function_type == "linear":
        required = {
            "input_min",
            "input_max",
            "utility_at_min",
            "utility_at_max",
        }
        if not required.issubset(value):
            raise ScenarioError(f"{path} linear function is incomplete")
        if value["input_min"] >= value["input_max"]:
            raise ScenarioError(f"{path} input_min must be less than input_max")
    elif function_type == "piecewise_linear":
        points = value.get("points")
        if not isinstance(points, list) or len(points) < 2:
            raise ScenarioError(f"{path}.points must contain at least two points")
        previous: float | None = None
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ScenarioError(f"{path}.points entries must be [input, utility]")
            if previous is not None and point[0] <= previous:
                raise ScenarioError(f"{path}.points inputs must increase strictly")
            previous = point[0]
    else:
        values = value.get("values")
        if not isinstance(values, dict) or not values:
            raise ScenarioError(f"{path}.values must be a non-empty object")


def _validate_dialogue_reasons(roles: dict[str, Any], definitions: dict[str, Any]) -> None:
    """Validate disclosure authoring without copying private sources into public data."""

    required = {"id", "term_id", "text", "source_ref", "disclose_when"}
    for role, data in roles.items():
        if "conversation_style" in data and (
            not isinstance(data["conversation_style"], str)
            or data["conversation_style"] not in CONVERSATION_STYLES
        ):
            raise ScenarioError(f"roles.{role}.conversation_style is not supported")
        reasons = data.get("dialogue_reasons", [])
        path = f"roles.{role}.dialogue_reasons"
        if not isinstance(reasons, list) or len(reasons) > 6:
            raise ScenarioError(f"{path} must be a list with at most six reasons")
        seen: set[str] = set()
        for index, reason in enumerate(reasons):
            item_path = f"{path}[{index}]"
            if not isinstance(reason, dict) or set(reason) != required:
                raise ScenarioError(f"{item_path} must contain exactly the reason fields")
            reason_id = reason["id"]
            if (
                not isinstance(reason_id, str)
                or len(reason_id) > 100
                or not _DIALOGUE_REASON_ID.fullmatch(reason_id)
            ):
                raise ScenarioError(f"{item_path}.id is invalid")
            if reason_id in seen:
                raise ScenarioError(f"{path} contains duplicate reason id {reason_id!r}")
            seen.add(reason_id)
            term_id = reason["term_id"]
            if not isinstance(term_id, str) or term_id not in definitions:
                raise ScenarioError(f"{item_path}.term_id references an undefined term")
            source_ref = reason["source_ref"]
            if source_ref not in ("brief.objective", "brief.context"):
                raise ScenarioError(f"{item_path}.source_ref must reference the same role brief")
            source = data.get("brief", {}).get(source_ref.split(".")[1])
            if not isinstance(source, str) or not source.strip():
                raise ScenarioError(f"{item_path}.source_ref references a missing source")
            if reason["disclose_when"] != "on_topic_question":
                raise ScenarioError(f"{item_path}.disclose_when must be on_topic_question")
            text = reason["text"]
            if (
                not isinstance(text, str)
                or not text.strip()
                or len(text) > 300
                or any(
                    char.isnumeric() or unicodedata.category(char)[0] == "C"
                    or unicodedata.category(char) == "Sc" or char == "%"
                    for char in text
                )
                or _DIALOGUE_REASON_NON_QUALITATIVE.search(text)
                or _DIALOGUE_REASON_UNSAFE_STRUCTURE.search(text)
            ):
                raise ScenarioError(f"{item_path}.text must be bounded plain nonnumeric text")


def _validate_dialogue_strategy(
    roles: dict[str, Any],
    opening_role: str,
    opening_terms: dict[str, Any],
) -> None:
    """Validate actor-safe dialogue goals separately from private role briefs."""

    required = {"shared_context", "opening_goal", "conversation_goal", "opening_term_ids"}
    optional = {"successful_history_context"}
    for role, data in roles.items():
        strategy = data.get("dialogue_strategy")
        if strategy is None:
            continue
        path = f"roles.{role}.dialogue_strategy"
        if role != opening_role:
            raise ScenarioError(f"{path} is supported only for the authored opening role")
        if (
            not isinstance(strategy, dict)
            or not required.issubset(strategy)
            or set(strategy) - required - optional
        ):
            raise ScenarioError(f"{path} has invalid fields")
        text_fields = required - {"opening_term_ids"} | (optional & set(strategy))
        for field in text_fields:
            value = strategy[field]
            limit = 800 if field.endswith("context") else 500
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > limit
                or any(
                    char.isnumeric()
                    or unicodedata.category(char)[0] == "C"
                    or unicodedata.category(char) == "Sc"
                    or char == "%"
                    for char in value
                )
                or _DIALOGUE_REASON_UNSAFE_STRUCTURE.search(value)
            ):
                raise ScenarioError(f"{path}.{field} must be bounded plain nonnumeric text")
        term_ids = strategy["opening_term_ids"]
        if (
            not isinstance(term_ids, list)
            or not 1 <= len(term_ids) <= 12
            or len(set(term_ids)) != len(term_ids)
            or any(term_id not in opening_terms for term_id in term_ids)
        ):
            raise ScenarioError(f"{path}.opening_term_ids must reference authored opening terms")


def _validate_exchange_policy(scenario: dict[str, Any]) -> None:
    if "exchange_policy" not in scenario:
        return
    policy = scenario["exchange_policy"]
    if not isinstance(policy, dict) or set(policy) != {"candidate_values"}:
        raise ScenarioError("exchange_policy must contain only candidate_values")
    values = policy["candidate_values"]
    if not isinstance(values, dict) or not 2 <= len(values) <= 12:
        raise ScenarioError("exchange_policy.candidate_values requires two to twelve terms")
    definitions = scenario["terms"]["definitions"]
    if not any(term in values for term in ("price", "annual_rent")):
        raise ScenarioError("exchange_policy requires an authored monetary term")
    count = 1
    for term_id, candidates in values.items():
        if term_id not in definitions or term_id not in scenario["terms"]["required_term_ids"]:
            raise ScenarioError("exchange_policy references an undefined or optional term")
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 16:
            raise ScenarioError(f"exchange_policy.{term_id} requires one to sixteen values")
        if len({canonical_json(value) for value in candidates}) != len(candidates):
            raise ScenarioError(f"exchange_policy.{term_id} contains duplicate values")
        validator = Draft202012Validator(definitions[term_id]["value_schema"])
        for value in candidates:
            if (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or list(validator.iter_errors(value))
            ):
                raise ScenarioError(f"exchange_policy.{term_id} contains an invalid numeric term")
        count *= len(candidates)
    if count > MAX_EXCHANGE_CANDIDATES:
        raise ScenarioError(f"exchange_policy exceeds {MAX_EXCHANGE_CANDIDATES} candidate packages")


def compile_scenario(document: dict[str, Any], path: Path) -> CompiledScenario:
    scenario = document["scenario"]
    if scenario["authoring_status"]["state"] != "published":
        raise ScenarioError(f"Scenario is not published: {path}")
    roles = scenario["roles"]
    if len(roles) != 2:
        raise ScenarioError("The MVP requires exactly two roles")
    if "negotiation_contract" in scenario and not is_supply_scenario(scenario):
        raise ScenarioError("Unsupported negotiation contract")
    if is_supply_scenario(scenario):
        errors = validate_supply_configuration(scenario)
        if errors:
            raise ScenarioError("Invalid supply configuration: " + ", ".join(errors))
    elif "supply_model" in scenario:
        raise ScenarioError("supply_model requires supply-package-v1")

    opening_role, opening_kind, opening_terms = authored_opening(scenario)
    required_terms = scenario["terms"]["required_term_ids"]
    missing = [term for term in required_terms if term not in opening_terms]
    if opening_kind == "opening_offer" and missing:
        raise ScenarioError(f"Opening offer is missing required terms: {', '.join(missing)}")
    if opening_kind == "opening_position" and not opening_terms:
        raise ScenarioError("Opening position must contain at least one authored term")
    if is_supply_scenario(scenario):
        if opening_kind != "opening_position":
            raise ScenarioError("Supply scenarios require an authored preliminary opening_position")
        errors = validate_supply_terms(scenario, opening_terms)
        if errors:
            raise ScenarioError("Invalid supply opening: " + ", ".join(errors))

    definitions = scenario["terms"]["definitions"]
    _validate_dialogue_reasons(roles, definitions)
    _validate_dialogue_strategy(roles, opening_role, opening_terms)
    _validate_exchange_policy(scenario)
    label = "Opening offer" if opening_kind == "opening_offer" else "Opening position"
    unknown_terms = [term for term in opening_terms if term not in definitions]
    if unknown_terms:
        raise ScenarioError(f"{label} contains undefined terms: {', '.join(unknown_terms)}")
    for term_id, value in opening_terms.items():
        validator = Draft202012Validator(definitions[term_id]["value_schema"])
        errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
        if errors:
            raise ScenarioError(f"{label} term {term_id!r} is invalid: {errors[0].message}")

    for index, constraint in enumerate(scenario["hard_constraints"]):
        if constraint["applies_to_role"] not in roles:
            raise ScenarioError(f"hard_constraints[{index}] references an unknown role")
        _validate_expression(constraint["expression"], f"hard_constraints[{index}].expression")

    role_models = scenario["utility_model"]["role_models"]
    if set(role_models) != set(roles):
        raise ScenarioError("utility_model.role_models must match scenario roles")
    for role, model in role_models.items():
        if is_supply_scenario(scenario):
            if model["aggregation"] != SUPPLY_EVALUATOR:
                raise ScenarioError("Supply role utility must use the authored supply evaluator")
            continue
        if model["aggregation"] not in {"weighted_sum", "piecewise_weighted_sum"} or not model["value_functions"]:
            raise ScenarioError("Scalar role utility requires supported nonempty value functions")
        for term_id, value_function in model["value_functions"].items():
            if term_id not in definitions:
                raise ScenarioError(f"Utility for {role} references undefined term {term_id}")
            if term_id not in required_terms:
                raise ScenarioError(
                    f"Utility for {role} references optional term {term_id}; "
                    "the MVP requires every utility-bearing term in required_term_ids"
                )
            _validate_value_function(
                value_function,
                f"utility_model.role_models.{role}.value_functions.{term_id}",
            )

    compiler_version = str(scenario["compiler"]["compiler_version"])
    compiled_projection = {
        "scenario": scenario,
        "opening_role": opening_role,
        "required_terms": required_terms,
        "compiler_version": compiler_version,
    }
    return CompiledScenario(
        source=scenario,
        source_path=path,
        content_digest=digest(document),
        compiled_digest=digest(compiled_projection),
        compiler_version=compiler_version,
    )


class ScenarioCatalog:
    def __init__(self, directories: Iterable[Path], schema_path: Path):
        self.directories = tuple(directories)
        self.schema_path = schema_path

    def discover(self) -> list[CompiledScenario]:
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        schema_validator = Draft202012Validator(schema)
        candidates: list[Path] = []
        for directory in self.directories:
            if not directory.exists():
                continue
            for suffix in ("*.yaml", "*.yml", "*.json"):
                candidates.extend(directory.rglob(suffix))

        seen: dict[tuple[str, int], Path] = {}
        compiled: list[CompiledScenario] = []
        for path in sorted(set(candidates)):
            document = _load_document(path)
            errors = sorted(
                schema_validator.iter_errors(document), key=lambda error: list(error.path)
            )
            if errors:
                where = ".".join(str(part) for part in errors[0].absolute_path)
                raise ScenarioError(f"{path}:{where}: {errors[0].message}")
            source = document["scenario"]
            key = (str(source["id"]), int(source["version"]))
            if key in seen:
                raise ScenarioError(
                    f"Duplicate scenario {key[0]} version {key[1]}: {seen[key]} and {path}"
                )
            seen[key] = path
            if source["authoring_status"]["state"] == "published":
                compiled.append(compile_scenario(document, path))
        return compiled


def _resolve_operand(expression: dict[str, Any], terms: dict[str, Any]) -> Any:
    if "term" in expression:
        term = expression["term"]
        if term not in terms:
            raise KeyError(term)
        return terms[term]
    if "const" in expression:
        return expression["const"]
    return evaluate_expression(expression, terms)


def evaluate_expression(expression: dict[str, Any], terms: dict[str, Any]) -> bool:
    try:
        operator = expression.get("op")
        if operator == "and":
            return all(evaluate_expression(item, terms) for item in expression["args"])
        if operator == "or":
            return any(evaluate_expression(item, terms) for item in expression["args"])
        if operator == "not":
            return not evaluate_expression(expression["arg"], terms)
        left = _resolve_operand(expression["left"], terms)
        right = _resolve_operand(expression["right"], terms)
        operations = {
            "eq": lambda: left == right,
            "ne": lambda: left != right,
            "lt": lambda: left < right,
            "lte": lambda: left <= right,
            "gt": lambda: left > right,
            "gte": lambda: left >= right,
            "in": lambda: left in right,
        }
        return bool(operations[operator]())
    except (KeyError, TypeError, ValueError):
        return False


def validate_terms(scenario: dict[str, Any], terms: dict[str, Any], complete: bool) -> list[str]:
    if is_supply_scenario(scenario):
        return validate_supply_terms(scenario, terms, complete)
    definitions = scenario["terms"]["definitions"]
    if any(term not in definitions for term in terms):
        return ["term_not_in_compiled_grammar"]
    violations: list[str] = []
    for term_id, value in terms.items():
        errors = list(Draft202012Validator(definitions[term_id]["value_schema"]).iter_errors(value))
        if errors:
            violations.append(f"invalid_term:{term_id}")
    if complete:
        for term_id in scenario["terms"]["required_term_ids"]:
            if term_id not in terms:
                violations.append(f"missing_required_term:{term_id}")
    return violations


def constraint_violations(scenario: dict[str, Any], role: str, terms: dict[str, Any]) -> list[str]:
    if is_supply_scenario(scenario):
        return supply_constraint_violations(scenario, role, terms)
    return [
        constraint.get("violation_code", constraint["id"])
        for constraint in scenario["hard_constraints"]
        if constraint["applies_to_role"] == role
        and not evaluate_expression(constraint["expression"], terms)
    ]


def _numeric_utility(function: dict[str, Any], value: float) -> float:
    if function["type"] == "linear":
        low = float(function["input_min"])
        high = float(function["input_max"])
        fraction = min(1.0, max(0.0, (float(value) - low) / (high - low)))
        return float(function["utility_at_min"]) + fraction * (
            float(function["utility_at_max"]) - float(function["utility_at_min"])
        )

    points = [(float(x), float(y)) for x, y in function["points"]]
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (left_x, left_y), (right_x, right_y) in zip(points, points[1:]):
        if left_x <= value <= right_x:
            fraction = (float(value) - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    raise AssertionError("piecewise interpolation did not find an interval")


def evaluate_utility(scenario: dict[str, Any], role: str, terms: dict[str, Any]) -> float:
    if is_supply_scenario(scenario):
        return evaluate_supply_utility(scenario, role, terms)
    model = scenario["utility_model"]["role_models"][role]
    weighted_sum = 0.0
    total_weight = 0.0
    for term_id, function in model["value_functions"].items():
        if term_id not in terms:
            continue
        weight = float(function["weight"])
        if function["type"] == "categorical":
            key = canonical_json(terms[term_id])
            raw = function["values"].get(key)
            if raw is None:
                raw = function["values"].get(str(terms[term_id]))
            if raw is None:
                raw = function.get("default_utility", 0)
            utility = float(raw)
        else:
            utility = _numeric_utility(function, float(terms[term_id]))
        weighted_sum += weight * utility
        total_weight += weight
    minimum = float(scenario["utility_model"]["normalization"]["minimum"])
    maximum = float(scenario["utility_model"]["normalization"]["maximum"])
    if total_weight == 0:
        return minimum
    return round(min(maximum, max(minimum, weighted_sum / total_weight)), 4)
