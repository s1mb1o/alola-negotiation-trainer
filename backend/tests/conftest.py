from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ID = "saas_subscription_ru"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "negotiation.sqlite3",
        scenario_directories=(PROJECT_ROOT / "examples",),
        scenario_schema_path=PROJECT_ROOT / "schemas" / "scenario-v1.schema.json",
        admin_token="test-admin",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def create_payload(
    key: str,
    *,
    difficulty: str = "normal",
    hints_enabled: bool = True,
    both_external: bool = False,
    language: str = "ru",
    human_role: str = "buyer",
) -> dict:
    other_role = "seller" if human_role == "buyer" else "buyer"
    controllers = {
        human_role: "external_agent" if both_external else "human",
        other_role: "external_agent" if both_external else "built_in_npc",
    }
    return {
        "idempotency_key": key,
        "scenario_id": SCENARIO_ID,
        "scenario_version": 1,
        "language": language,
        "participants": [
            {"role": "buyer", "controller": controllers["buyer"]},
            {"role": "seller", "controller": controllers["seller"]},
        ],
        "difficulty": difficulty,
        "hints_enabled": hints_enabled,
        "run_mode": "training",
    }


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def credentials(response: dict) -> dict[str, str]:
    return {item["role"]: item["token"] for item in response["participant_credentials"]}
