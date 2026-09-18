from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from backend.app.scenarios import ScenarioError, compile_scenario

from .conftest import PROJECT_ROOT


VERSION_PAIRS = [
    (
        "scenario_supplier_001_v3.yaml", "scenario_supplier_001_v4.yaml",
        "f2ecb2dfca6bf5998b8450030bc1b440e7a71d3f426629520cd521d56e06952a",
    ),
    (
        "scenario_office_lease_ru_v2.yaml", "scenario_office_lease_ru_v3.yaml",
        "654faba056f073f2cd417a37d5dea8b93893413d76ea2acb45ad172a3b0d4bd6",
    ),
    (
        "scenario_office_lease_en_v2.yaml", "scenario_office_lease_en_v3.yaml",
        "612d41a2b4a71979b091b40feda7f2fe95e8a25929fe122680bc41378a6218dc",
    ),
    (
        "scenario_freight_contract_ru.yaml", "scenario_freight_contract_ru_v2.yaml",
        "670becf9da437bebc242606a978fbc8bc3082bb847d6cb0f65f01952c3fc0044",
    ),
    (
        "scenario_freight_contract_en.yaml", "scenario_freight_contract_en_v2.yaml",
        "8a77abacf1fd889dbafb87d6f34a4f87928403212abb0b36909c6b8b4581ed20",
    ),
    (
        "scenario_saas_subscription_ru.yaml", "scenario_saas_subscription_ru_v2.yaml",
        "f695049f5308eb460aad94e06fd6551afca04f69a05f26d30de53e545e6dc7c8",
    ),
    (
        "scenario_saas_subscription_en.yaml", "scenario_saas_subscription_en_v2.yaml",
        "3e8f181639faa9e43ae29f84f5c23fe3a0459abcee29f0a4ea99f237a77bae42",
    ),
]


def _document(filename: str = "scenario_supplier_001_v4.yaml") -> dict:
    return yaml.safe_load((PROJECT_ROOT / "examples" / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("old_name", "new_name", "old_sha256"), VERSION_PAIRS)
def test_reason_versions_preserve_immutable_sources_and_all_economic_rules(
    old_name: str, new_name: str, old_sha256: str,
) -> None:
    old_path = PROJECT_ROOT / "examples" / old_name
    assert hashlib.sha256(old_path.read_bytes()).hexdigest() == old_sha256
    previous = _document(old_name)
    current = _document(new_name)
    schema = json.loads((PROJECT_ROOT / "schemas/scenario-v1.schema.json").read_text())
    Draft202012Validator(schema).validate(current)
    old_compiled = compile_scenario(previous, old_path)
    new_compiled = compile_scenario(current, PROJECT_ROOT / "examples" / new_name)
    assert new_compiled.version == old_compiled.version + 1
    assert new_compiled.compiler_version == old_compiled.compiler_version
    assert new_compiled.content_digest != old_compiled.content_digest
    assert new_compiled.compiled_digest != old_compiled.compiled_digest

    without_reasons = deepcopy(current)
    without_reasons["scenario"]["version"] = previous["scenario"]["version"]
    for role in without_reasons["scenario"]["roles"].values():
        reasons = role.pop("dialogue_reasons")
        assert 2 <= len(reasons) <= 6
        assert all(reason["disclose_when"] == "on_topic_question" for reason in reasons)
    # Exact equality also covers openings, limits, utility functions, knowledge, and BATNA.
    assert without_reasons == previous
    assert "dialogue_reasons" not in json.dumps(new_compiled.public_metadata())


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("id", "Bad-ID", "id is invalid"),
        ("id", "x" * 101, "id is invalid"),
        ("term_id", "unauthored_term", "undefined term"),
        ("source_ref", "roles.buyer.brief.context", "same role brief"),
        ("source_ref", "batna.description", "same role brief"),
        ("disclose_when", "always", "on_topic_question"),
        ("text", "", "plain nonnumeric"),
        ("text", " " * 10, "plain nonnumeric"),
        ("text", "a" * 301, "plain nonnumeric"),
        ("text", "Нам нужно 50 процентов предоплаты.", "plain nonnumeric"),
        ("text", "Нам нужно пять процентов предоплаты.", "plain nonnumeric"),
        ("text", "Payment in EUR matters.", "plain nonnumeric"),
        ("text", "Оплата в евро важна.", "plain nonnumeric"),
        ("text", "Payment in ₹ matters.", "plain nonnumeric"),
        ("text", "Delivery in December matters.", "plain nonnumeric"),
        ("text", "Поставка в декабре важна.", "plain nonnumeric"),
        ("text", "Ранняя оплата.\nНовая строка.", "plain nonnumeric"),
        ("text", "Ранняя оплата\u200b важна.", "plain nonnumeric"),
        ("text", "<strong>Ранняя оплата важна.</strong>", "plain nonnumeric"),
        ("text", "**Ранняя оплата важна.**", "plain nonnumeric"),
        ("text", "[Оплата](https://example.test)", "plain nonnumeric"),
        ("text", "Bearer synthetic-secret-value", "plain nonnumeric"),
        ("text", "sk-synthetic-secret-value", "plain nonnumeric"),
    ],
)
def test_compiler_rejects_invalid_authored_reasons(field: str, value: object, error: str) -> None:
    document = _document()
    document["scenario"]["roles"]["seller"]["dialogue_reasons"][0][field] = value
    with pytest.raises(ScenarioError, match=error):
        compile_scenario(document, Path("invalid-reason.yaml"))


def test_compiler_rejects_duplicate_reason_ids_and_unbounded_reason_lists() -> None:
    document = _document()
    reasons = document["scenario"]["roles"]["seller"]["dialogue_reasons"]
    reasons.append(deepcopy(reasons[0]))
    with pytest.raises(ScenarioError, match="duplicate reason id"):
        compile_scenario(document, Path("duplicate-reason.yaml"))

    reasons[:] = [dict(reasons[0], id=f"reason_{index}") for index in range(7)]
    with pytest.raises(ScenarioError, match="at most six"):
        compile_scenario(document, Path("too-many-reasons.yaml"))


def test_compiler_rejects_missing_private_source_and_extra_reason_fields() -> None:
    document = _document()
    seller = document["scenario"]["roles"]["seller"]
    seller["brief"]["objective"] = ""
    with pytest.raises(ScenarioError, match="missing source"):
        compile_scenario(document, Path("missing-reason-source.yaml"))

    document = _document()
    document["scenario"]["roles"]["seller"]["dialogue_reasons"][0]["secret"] = "not allowed"
    with pytest.raises(ScenarioError, match="exactly the reason fields"):
        compile_scenario(document, Path("extra-reason-field.yaml"))


@pytest.mark.parametrize(("old_name", "new_name", "_old_sha256"), VERSION_PAIRS)
def test_latest_catalog_selects_reason_version_and_preserves_replay_version(
    client: TestClient, old_name: str, new_name: str, _old_sha256: str,
) -> None:
    current = _document(new_name)["scenario"]
    previous = _document(old_name)["scenario"]
    latest = client.get(f"/api/v1/scenarios/{current['id']}")
    historical = client.get(
        f"/api/v1/scenarios/{previous['id']}/versions/{previous['version']}"
    )
    assert latest.status_code == historical.status_code == 200
    assert latest.json()["version"] == current["version"] + 1
    assert historical.json()["version"] == previous["version"]
    assert "dialogue_reasons" not in latest.text
    for role in current["roles"].values():
        for reason in role["dialogue_reasons"]:
            assert reason["text"] not in latest.text
