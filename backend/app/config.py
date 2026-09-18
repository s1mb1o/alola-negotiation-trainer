from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re


_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _bounded_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _bounded_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _bounded_optional_float(name: str, *, minimum: float, maximum: float) -> float | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    scenario_directories: tuple[Path, ...]
    scenario_schema_path: Path
    admin_token: str
    npc_provider: str = "template"
    npc_model: str | None = None
    npc_api_key_env: str | None = None
    npc_base_url: str | None = None
    npc_max_output_tokens: int = 300
    npc_temperature: float | None = None
    npc_timeout_seconds: float = 20.0
    supply_semantic_extraction: bool = False

    @classmethod
    def from_environment(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        configured_dirs = os.getenv("NEGOTIATION_SCENARIO_DIR")
        if configured_dirs:
            scenario_directories = tuple(
                Path(value).expanduser().resolve()
                for value in configured_dirs.split(os.pathsep)
                if value
            )
        else:
            scenario_directories = (
                project_root / "examples",
                project_root / "backend" / "data" / "scenarios",
            )

        database_path = Path(
            os.getenv(
                "NEGOTIATION_DB_PATH",
                str(project_root / "backend" / "data" / "negotiation.db"),
            )
        ).expanduser()
        npc_provider = os.getenv("NEGOTIATION_NPC_PROVIDER", "template").strip().lower()
        if npc_provider not in {"template", "openai", "qwen"}:
            raise ValueError("NEGOTIATION_NPC_PROVIDER must be template, openai, or qwen")
        npc_model = os.getenv("NEGOTIATION_NPC_MODEL") or None
        npc_api_key_env = os.getenv("NEGOTIATION_NPC_API_KEY_ENV") or None
        if npc_api_key_env is not None and not _ENV_NAME.fullmatch(npc_api_key_env):
            raise ValueError("NEGOTIATION_NPC_API_KEY_ENV must be an environment variable name")
        npc_base_url = os.getenv("NEGOTIATION_NPC_BASE_URL") or None
        if npc_base_url is not None:
            if not npc_base_url.startswith("https://"):
                raise ValueError("NEGOTIATION_NPC_BASE_URL must use HTTPS")
            if npc_api_key_env is None:
                raise ValueError(
                    "A custom NEGOTIATION_NPC_BASE_URL requires explicit "
                    "NEGOTIATION_NPC_API_KEY_ENV"
                )

        return cls(
            database_path=database_path.resolve(),
            scenario_directories=scenario_directories,
            scenario_schema_path=project_root / "schemas" / "scenario-v1.schema.json",
            admin_token=os.getenv("NEGOTIATION_ADMIN_TOKEN", ""),
            npc_provider=npc_provider,
            npc_model=npc_model,
            npc_api_key_env=npc_api_key_env,
            npc_base_url=npc_base_url,
            npc_max_output_tokens=_bounded_int(
                "NEGOTIATION_NPC_MAX_OUTPUT_TOKENS", 300, minimum=32, maximum=2_000
            ),
            npc_temperature=_bounded_optional_float(
                "NEGOTIATION_NPC_TEMPERATURE", minimum=0.0, maximum=2.0
            ),
            npc_timeout_seconds=_bounded_float(
                "NEGOTIATION_NPC_TIMEOUT_SECONDS", 20.0, minimum=0.1, maximum=120.0
            ),
            supply_semantic_extraction=os.getenv("NEGOTIATION_SUPPLY_SEMANTIC_EXTRACTION", "false").lower() == "true",
        )
