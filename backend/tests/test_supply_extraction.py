from copy import deepcopy
import pytest
from pathlib import Path

from backend.app.supply_extraction import LlmSupplyExtractor
from backend.app.supply_language import SupplyAction
from backend.app.scenarios import ScenarioCatalog
from backend.tests.test_supply_dialogue import SupplyProvider
from backend.tests.test_supply_protocol import create_supply
from backend.tests.conftest import bearer, credentials


@pytest.mark.parametrize(
    "message",
    [
        "I am not offering 110000.",
        "We previously offered 110000.",
        "Раньше предлагали 110000.",
        "Не предлагаю 110000.",
        "Could we offer 110000?",
    ],
)
def test_semantic_model_cannot_override_explicit_non_amendment(message):
    doc = scenario()
    provider = SupplyProvider([])
    result = LlmSupplyExtractor(provider).extract(
        message, "en", doc["roles"]["seller"]["opening_position"], 1, doc
    )
    assert result.terms is None
    assert provider.calls == []


def scenario():
    root = Path(__file__).resolve().parents[2]
    return next(
        item.source
        for item in ScenarioCatalog(
            (root / "examples",), root / "schemas/scenario-v1.schema.json"
        ).discover()
        if item.source["id"] == "supplier_integration_ru"
    )


def test_semantic_normalization_reenters_typed_parser_and_requires_equivalence():
    doc = scenario()
    terms = doc["roles"]["seller"]["opening_position"]
    original = deepcopy(terms)
    provider = SupplyProvider(
        [
            {"source_revision": 7, "intent": "amend", "canonical_message": "Предлагаем 110000 EUR"},
            {"equivalent": True},
        ]
    )
    action = LlmSupplyExtractor(provider).extract(
        "За партию предлагаю сумму 110000.", "ru", terms, 7, doc
    )
    assert action.action == "amend" and action.terms["base_price"]["minor_units"] == 11000000
    assert action.source_revision == 7
    assert terms == original
    assert len(provider.calls) == 2


def test_extraction_rejects_invented_numbers_stale_revision_refusal_and_unsupported_condition():
    doc = scenario()
    terms = doc["roles"]["seller"]["opening_position"]
    for output in [
        {"source_revision": 1, "intent": "amend", "canonical_message": "Предлагаем 100000 EUR"},
        {"source_revision": 2, "intent": "amend", "canonical_message": "Предлагаем 110000 EUR"},
        {"refusal": "Cannot help"},
    ]:
        provider = SupplyProvider([output])
        action = LlmSupplyExtractor(provider).extract(
            "За партию предлагаю сумму 110000.", "ru", terms, 1, doc
        )
        assert action.clarification_code == "extraction_unavailable"
        assert action.terms is None
    provider = SupplyProvider([])
    action = LlmSupplyExtractor(provider).extract("110000 если совет одобрит", "ru", terms, 1, doc)
    assert action.clarification_code == "extraction_unavailable" and not provider.calls


def test_optional_extractor_checks_auth_revision_idempotency_before_calls_and_runs_outside_write(
    client,
):
    session = create_supply(client)
    token = credentials(session)["buyer"]
    service = client.app.state.service

    class Extractor:
        calls = 0

        def extract(self, message, language, terms, revision, doc):
            self.calls += 1
            with service.database.write_transaction() as connection:
                connection.execute("SELECT 1")
            return SupplyAction("inform", source_revision=revision)

    extractor = Extractor()
    service.supply_extractor = extractor
    route = f"/api/v1/sessions/{session['session_id']}/messages"
    body = {
        "message": "Это важно для запуска проекта.",
        "expected_revision": session["revision"],
        "idempotency_key": "extract-once",
    }
    assert client.post(route, json=body, headers=bearer("wrong-token")).status_code == 401
    assert (
        client.post(
            route,
            json={**body, "expected_revision": 999, "idempotency_key": "stale-check"},
            headers=bearer(token),
        ).status_code
        == 409
    )
    assert extractor.calls == 0
    assert client.post(route, json=body, headers=bearer(token)).status_code == 200
    assert client.post(route, json=body, headers=bearer(token)).status_code == 200
    assert extractor.calls == 1
