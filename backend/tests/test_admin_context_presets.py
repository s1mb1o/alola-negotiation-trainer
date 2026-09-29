from dataclasses import replace
import json

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.app.training import authored_tone_options
from .conftest import bearer, create_payload

ENDPOINT = "/api/v1/admin/training-presets"


def presets(client, language="ru"):
    response = client.get(ENDPOINT, params={"language": language}, headers=bearer("test-admin"))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["items"]


def create_from_preset(client, preset, key, *, profile="concise_skeptical", difficulty="normal"):
    source = preset["scenario"]
    human_role = next(item["role"] for item in source["roles"] if item["role"] != preset["npc_role"])
    body = create_payload(key, language=source["language"], human_role=human_role, difficulty=difficulty)
    body.update(scenario_id=source["id"], scenario_version=source["version"],
                training={"profile": profile, "authored_tone": True})
    response = client.post("/api/v1/sessions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def stored_state(client, session):
    with client.app.state.database.read_connection() as connection:
        return json.loads(connection.execute("SELECT state_json FROM sessions WHERE id = ?",
                                            (session["session_id"],)).fetchone()[0])


def test_catalog_requires_admin_and_disabled_access_fails_closed(client, settings):
    assert client.get(ENDPOINT).status_code == 401
    assert client.get(ENDPOINT, headers=bearer("wrong")).status_code == 401
    player = client.post("/api/v1/sessions", json=create_payload("player-catalog-access")).json()
    assert client.get(ENDPOINT, headers=bearer(player["participant_token"])).status_code == 401
    with TestClient(create_app(replace(settings, admin_token=""))) as disabled:
        assert disabled.get(ENDPOINT).status_code == 503
    assert client.get(ENDPOINT, params={"language": "fr"}, headers=bearer("test-admin")).status_code == 422


@pytest.mark.parametrize("language", ["ru", "en"])
def test_catalog_matches_authored_goals_and_pins_versions(client, language):
    items = presets(client, language)
    assert {item["domain_id"] for item in items} == {"equipment", "software", "logistics", "property"}
    assert len({item["preset_id"] for item in items}) == len(items)
    for item in items:
        scenario = item["scenario"]
        assert scenario["language"] == language
        with client.app.state.database.read_connection() as connection:
            row = connection.execute("SELECT source_json FROM scenario_versions WHERE scenario_id = ? AND version = ?",
                                     (scenario["id"], scenario["version"])).fetchone()
        source = json.loads(row["source_json"])
        assert item["npc_goal"] == source["roles"][item["npc_role"]]["brief"]["objective"]
        assert set(item) == {"preset_id", "domain_id", "domain", "topic_id", "topic", "npc_role", "npc_goal", "scenario"}
        assert "utility_model" not in scenario and "brief" not in json.dumps(scenario)
    assert "npc_goal" not in client.get("/api/v1/scenarios").text


def test_goal_selection_changes_real_contract_and_player_handoff_is_safe(client):
    catalog = presets(client)
    selected = [next(p for p in catalog if p["scenario"]["id"] == scenario and p["npc_role"] == "seller")
                for scenario in ("supplier_001", "supplier_integration_ru")]
    sessions = [create_from_preset(client, preset, f"preset-goal-{index}")
                for index, preset in enumerate(selected)]
    assert "price" in stored_state(client, sessions[0])["opening_terms"]
    assert "base_price" in sessions[1]["observation"]["current_public_terms"]
    for preset, session in zip(selected, sessions):
        assert session["scenario_version"] == preset["scenario"]["version"]
        assert session["observation"]["role"] == "buyer"
        assert "npc_goal" not in json.dumps(session)
        assert preset["npc_goal"] not in json.dumps(session, ensure_ascii=False)
        assert client.get(ENDPOINT, headers=bearer(session["participant_token"])).status_code == 401
    buyer_npc = next(p for p in catalog if p["scenario"]["id"] == "supplier_001" and p["npc_role"] == "buyer")
    swapped = create_from_preset(client, buyer_npc, "admin-swapped-role")
    assert swapped["observation"]["role"] == "seller"


def send(client, session, message, key):
    result = client.post(f"/api/v1/sessions/{session['session_id']}/messages",
                         headers=bearer(session["participant_token"]), json={
                             "expected_revision": session["revision"], "idempotency_key": key,
                             "message": message,
                         })
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize("scenario", ["supplier_001", "supplier_integration_ru", "saas_subscription_en"])
def test_authored_tone_changes_template_words_not_economics(client, scenario):
    language = "en" if scenario.endswith("_en") else "ru"
    preset = next(p for p in presets(client, language) if p["scenario"]["id"] == scenario and p["npc_role"] == "seller")
    sessions = [create_from_preset(client, preset, f"tone-{scenario}-{profile}", profile=profile)
                for profile in ("concise_skeptical", "sociable")]
    assert sessions[0]["observation"]["conversation"] != sessions[1]["observation"]["conversation"]
    question = "Какие ваши приоритеты?" if language == "ru" else "What are your priorities?"
    replies = [send(client, session, question, f"tone-question-{index}") for index, session in enumerate(sessions)]
    for left, right in ((sessions[0], sessions[1]), (replies[0], replies[1])):
        assert left["status"] == right["status"]
        assert left["observation"].get("current_public_terms") == right["observation"].get("current_public_terms")
        assert stored_state(client, left)["opening_terms"] == stored_state(client, right)["opening_terms"]
    assert replies[0]["observation"]["conversation"][-1]["message"] != replies[1]["observation"]["conversation"][-1]["message"]
    assert stored_state(client, sessions[1])["training"]["setup"]["authored_tone"] is True


def test_tone_preserves_legacy_and_binding_words():
    options = ("Exact original text.",)
    assert authored_tone_options(options, {"profile": "sociable"}, "en", "general_answer") == options
    assert authored_tone_options(options, {"profile": "sociable", "authored_tone": True}, "en", "accept") == options
    assert authored_tone_options(options, {"profile": "concise_skeptical", "authored_tone": True}, "en", "general_answer") == options


@pytest.mark.parametrize("language", ["ru", "en"])
def test_every_published_preset_starts_the_selected_role(client, language):
    for index, preset in enumerate(presets(client, language)):
        session = create_from_preset(client, preset, f"all-presets-{language}-{index}")
        assert session["observation"]["role"] != preset["npc_role"]
        assert session["scenario_version"] == preset["scenario"]["version"]


def test_difficulty_remains_effective_and_tone_survives_restart_and_fork(client, settings):
    preset = next(p for p in presets(client) if p["scenario"]["id"] == "supplier_001" and p["npc_role"] == "seller")
    guided = create_from_preset(client, preset, "preset-guided", profile="sociable", difficulty="guided")
    expert = create_from_preset(client, preset, "preset-expert", difficulty="expert")
    assert guided["observation"]["assistance"]["coaching"]
    assert expert["observation"]["assistance"] is None
    send(client, guided, "Прекращаю переговоры.", "preset-stop")
    with TestClient(create_app(settings)) as restarted:
        child = restarted.post(f"/api/v1/sessions/{guided['session_id']}/fork",
                               headers=bearer(guided["participant_token"]),
                               json={"source_revision": 0, "idempotency_key": "preset-fork"})
        assert child.status_code == 201, child.text
        assert stored_state(restarted, child.json())["training"]["setup"]["authored_tone"] is True
        assert stored_state(restarted, child.json())["training"]["setup"]["profile"] == "sociable"
