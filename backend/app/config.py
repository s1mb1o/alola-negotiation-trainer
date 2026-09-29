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


def _optional_bool(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    value = raw.strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


def _provider_name(name: str, *, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    value = default if raw is None else raw.strip().lower()
    if value in {None, ""}:
        return None
    if value not in {"template", "openai", "qwen"}:
        raise ValueError(f"{name} must be template, openai, or qwen")
    return value


def _provider_endpoint(prefix: str) -> tuple[str | None, str | None]:
    key_name = os.getenv(f"{prefix}_API_KEY_ENV") or None
    if key_name is not None and not _ENV_NAME.fullmatch(key_name):
        raise ValueError(f"{prefix}_API_KEY_ENV must be an environment variable name")
    base_url = os.getenv(f"{prefix}_BASE_URL") or None
    if base_url is not None:
        if not base_url.startswith("https://"):
            raise ValueError(f"{prefix}_BASE_URL must use HTTPS")
        if key_name is None:
            raise ValueError(f"A custom {prefix}_BASE_URL requires explicit {prefix}_API_KEY_ENV")
    return key_name, base_url


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
    npc_enable_thinking: bool | None = None
    npc_timeout_seconds: float = 20.0
    control_provider: str | None = None
    control_model: str | None = None
    control_api_key_env: str | None = None
    control_base_url: str | None = None
    control_temperature: float | None = None
    control_enable_thinking: bool | None = None
    control_timeout_seconds: float = 20.0
    review_provider: str | None = None
    review_model: str | None = None
    review_api_key_env: str | None = None
    review_base_url: str | None = None
    review_temperature: float | None = None
    review_enable_thinking: bool | None = None
    review_timeout_seconds: float = 45.0
    supply_semantic_extraction: bool = False
    llm_trace_enabled: bool = False
    npc_relevance_check: bool = True

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
        npc_provider = _provider_name("NEGOTIATION_NPC_PROVIDER", default="template")
        assert npc_provider is not None
        npc_model = os.getenv("NEGOTIATION_NPC_MODEL") or None
        npc_api_key_env, npc_base_url = _provider_endpoint("NEGOTIATION_NPC")
        control_provider = _provider_name("NEGOTIATION_CONTROL_PROVIDER")
        control_api_key_env, control_base_url = _provider_endpoint("NEGOTIATION_CONTROL")
        review_provider = _provider_name("NEGOTIATION_REVIEW_PROVIDER")
        review_api_key_env, review_base_url = _provider_endpoint("NEGOTIATION_REVIEW")

        return cls(
            database_path=database_path.resolve(),
            scenario_directories=scenario_directories,
            scenario_schema_path=project_root / "schemas" / "scenario-v1.schema.json",
            admin_token=os.getenv("NEGOTIATION_ADMIN_TOKEN", ""),
            npc_provider=npc_provider,
            npc_relevance_check=_optional_bool("NEGOTIATION_NPC_RELEVANCE_CHECK") is not False,
            npc_model=npc_model,
            npc_api_key_env=npc_api_key_env,
            npc_base_url=npc_base_url,
            npc_max_output_tokens=_bounded_int(
                "NEGOTIATION_NPC_MAX_OUTPUT_TOKENS", 300, minimum=32, maximum=2_000
            ),
            npc_temperature=_bounded_optional_float(
                "NEGOTIATION_NPC_TEMPERATURE", minimum=0.0, maximum=2.0
            ),
            npc_enable_thinking=_optional_bool("NEGOTIATION_NPC_ENABLE_THINKING"),
            npc_timeout_seconds=_bounded_float(
                "NEGOTIATION_NPC_TIMEOUT_SECONDS", 20.0, minimum=0.1, maximum=120.0
            ),
            control_provider=control_provider,
            control_model=os.getenv("NEGOTIATION_CONTROL_MODEL") or None,
            control_api_key_env=control_api_key_env,
            control_base_url=control_base_url,
            control_temperature=_bounded_optional_float(
                "NEGOTIATION_CONTROL_TEMPERATURE", minimum=0.0, maximum=2.0
            ),
            control_enable_thinking=_optional_bool("NEGOTIATION_CONTROL_ENABLE_THINKING"),
            control_timeout_seconds=_bounded_float(
                "NEGOTIATION_CONTROL_TIMEOUT_SECONDS", 20.0, minimum=0.1, maximum=120.0
            ),
            review_provider=review_provider,
            review_model=os.getenv("NEGOTIATION_REVIEW_MODEL") or None,
            review_api_key_env=review_api_key_env,
            review_base_url=review_base_url,
            review_temperature=_bounded_optional_float(
                "NEGOTIATION_REVIEW_TEMPERATURE", minimum=0.0, maximum=2.0
            ),
            review_enable_thinking=_optional_bool("NEGOTIATION_REVIEW_ENABLE_THINKING"),
            review_timeout_seconds=_bounded_float(
                "NEGOTIATION_REVIEW_TIMEOUT_SECONDS", 45.0, minimum=0.1, maximum=120.0
            ),
            supply_semantic_extraction=os.getenv("NEGOTIATION_SUPPLY_SEMANTIC_EXTRACTION", "false").lower() == "true",
            llm_trace_enabled=os.getenv("NEGOTIATION_LLM_TRACE", "false").lower() == "true",
        )
