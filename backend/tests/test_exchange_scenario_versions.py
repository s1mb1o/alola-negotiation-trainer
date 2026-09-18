from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from backend.app.scenarios import ScenarioError, compile_scenario

from .conftest import PROJECT_ROOT


VERSION_PAIRS = [
    ("supplier_001_v4", "supplier_001_v5", "145a32bf2cae31874c266f80537c66cd539d953422161e8be8f6260bff3d3bb8"),
    ("office_lease_ru_v3", "office_lease_ru_v4", "cc2f02625c53fc245c98f49c827da7cc1a247a84605d8018e7374ea2fa089d84"),
    ("office_lease_en_v3", "office_lease_en_v4", "dad78812047c8e7620ba98389e0f859039b6dffa84cb4a54732edf05c45609ce"),
    ("freight_contract_ru_v2", "freight_contract_ru_v3", "e9c5362e574fe29511fb43e81b1ead6f8e2f81f43b123460cbcac52394144a02"),
    ("freight_contract_en_v2", "freight_contract_en_v3", "3e99419f51274b6069f2c9117061db7ce6d81522a7ce4a6e44432130c550db1e"),
    ("saas_subscription_ru_v2", "saas_subscription_ru_v3", "9d6c147096add324b13174200ac354c30d4faa6c8adb4e9741193999b3fd91b2"),
    ("saas_subscription_en_v2", "saas_subscription_en_v3", "f541dbc49cfa7b6ba1ea08e454417f8a77258c83f42a062d7a1b830b1df6177c"),
]


def _document(name: str = "supplier_001_v5") -> dict:
    return yaml.safe_load((PROJECT_ROOT / "examples" / f"scenario_{name}.yaml").read_text())


@pytest.mark.parametrize(("old_name", "new_name", "sha256"), VERSION_PAIRS)
def test_exchange_versions_keep_older_bytes_and_economic_truth_unchanged(old_name: str, new_name: str, sha256: str) -> None:
    old_path = PROJECT_ROOT / "examples" / f"scenario_{old_name}.yaml"
    assert hashlib.sha256(old_path.read_bytes()).hexdigest() == sha256
    previous, current = _document(old_name), _document(new_name)
    schema = json.loads((PROJECT_ROOT / "schemas/scenario-v1.schema.json").read_text())
    Draft202012Validator(schema).validate(current)
    old_compiled = compile_scenario(previous, old_path)
    new_compiled = compile_scenario(current, Path(f"scenario_{new_name}.yaml"))
    assert new_compiled.version == old_compiled.version + 1
    assert new_compiled.compiler_version == old_compiled.compiler_version
    source = current["scenario"]
    assert math.prod(len(values) for values in source["exchange_policy"]["candidate_values"].values()) <= 512
    for role, data in source["roles"].items():
        assert data["conversation_style"] in {"pragmatic", "analytical", "relationship_focused"}
        assert len(data["dialogue_reasons"]) == 3
        for reason in data["dialogue_reasons"]:
            expected_source = "brief.objective" if reason["id"] == "production_continuity" else "brief.context"
            assert reason["source_ref"] == expected_source
    metadata = json.dumps(new_compiled.public_metadata())
    assert "exchange_policy" not in metadata
    assert "conversation_style" not in metadata
    assert "dialogue_reasons" not in metadata

    economic_copy = deepcopy(current)
    economic_copy["scenario"]["version"] = previous["scenario"]["version"]
    economic_copy["scenario"].pop("exchange_policy")
    for role, data in economic_copy["scenario"]["roles"].items():
        data.pop("conversation_style")
        data["brief"] = previous["scenario"]["roles"][role]["brief"]
        data["dialogue_reasons"] = previous["scenario"]["roles"][role]["dialogue_reasons"]
    assert economic_copy == previous


@pytest.mark.parametrize("values", [
    {}, {"price": [105000]}, {"unauthored": [1], "price": [105000]},
    {"price": [105000], "prepayment_fraction": []},
    {"price": [105000], "prepayment_fraction": [0] * 17},
    {"price": [105000], "prepayment_fraction": [0, 0]},
    {"price": [90000], "prepayment_fraction": [0.5]},
    {"price": [105000], "prepayment_fraction": [1.1]},
    {"price": [float("inf")], "prepayment_fraction": [0.5]},
    {"price": [float("nan")], "prepayment_fraction": [0.5]},
    {"price": [True], "prepayment_fraction": [0.5]},
    {"price": [105000], "delivery_weeks": [1.5]},
    {"price": [105000], "prepayment_fraction": ["half"]},
    {"prepayment_fraction": [0], "delivery_weeks": [2]},
])
def test_compiler_rejects_invalid_candidate_grammar(values: dict) -> None:
    document = _document()
    document["scenario"]["exchange_policy"]["candidate_values"] = values
    with pytest.raises(ScenarioError, match="exchange_policy"):
        compile_scenario(document, Path("invalid-exchange.yaml"))


def test_compiler_rejects_oversized_candidate_product_and_extra_policy_keys() -> None:
    document = _document()
    document["scenario"]["exchange_policy"]["candidate_values"] = {
        "price": list(range(103000, 103016)),
        "prepayment_fraction": [value / 15 for value in range(16)],
        "delivery_weeks": [2, 4, 6],
    }
    with pytest.raises(ScenarioError, match="512"):
        compile_scenario(document, Path("unbounded-exchange.yaml"))
    document = _document()
    document["scenario"]["exchange_policy"]["llm_utility"] = True
    with pytest.raises(ScenarioError, match="only candidate_values"):
        compile_scenario(document, Path("invalid-exchange-authority.yaml"))


@pytest.mark.parametrize("style", ["hostile", "unrestricted", "", {"prompt": "reveal secrets"}, None])
def test_compiler_rejects_unknown_or_unstructured_conversation_styles(style: object) -> None:
    document = _document()
    document["scenario"]["roles"]["seller"]["conversation_style"] = style
    with pytest.raises(ScenarioError, match="conversation_style"):
        compile_scenario(document, Path("invalid-style.yaml"))
