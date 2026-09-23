from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .training import TrainingSetup


class Difficulty(StrEnum):
    guided = "guided"
    easy = "easy"
    normal = "normal"
    expert = "expert"


class Controller(StrEnum):
    human = "human"
    external_agent = "external_agent"
    built_in_npc = "built_in_npc"
    scripted_bot = "scripted_bot"


class RunMode(StrEnum):
    training = "training"
    benchmark = "benchmark"


class ParticipantSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    controller: Controller
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    prompt_version: str | None = Field(default=None, min_length=1, max_length=100)


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    scenario_version: int = Field(default=1, ge=1)
    language: Literal["ru", "en"] = "ru"
    participants: list[ParticipantSpec]
    difficulty: Difficulty = Difficulty.normal
    hints_enabled: bool = True
    run_mode: RunMode = RunMode.training
    benchmark_run_id: str | None = Field(default=None, min_length=1, max_length=128)
    trial_id: str | None = Field(default=None, min_length=1, max_length=128)
    benchmark_expected_trials: int | None = Field(default=None, ge=1, le=100_000)
    seed: int | None = None
    training: TrainingSetup | None = None

    @model_validator(mode="after")
    def validate_participants(self) -> "CreateSessionRequest":
        if self.training is not None and (
            self.run_mode != RunMode.training
            or sorted(str(item.controller) for item in self.participants) != ["built_in_npc", "human"]
        ):
            raise ValueError("Training context requires one human and one built-in NPC in training mode")
        if len(self.participants) != 2:
            raise ValueError("The MVP requires exactly two participants")
        roles = [participant.role for participant in self.participants]
        if len(set(roles)) != len(roles):
            raise ValueError("Participant roles must be unique")
        if all(
            participant.controller == Controller.built_in_npc for participant in self.participants
        ):
            raise ValueError("At least one participant must use an external controller")
        if self.run_mode == RunMode.benchmark:
            if self.hints_enabled or self.difficulty != Difficulty.normal:
                raise ValueError("Benchmark sessions require normal difficulty and disabled hints")
            if not self.benchmark_run_id or not self.trial_id or not self.benchmark_expected_trials:
                raise ValueError(
                    "Benchmark sessions require benchmark_run_id, trial_id, and "
                    "benchmark_expected_trials"
                )
        return self


class SubmitMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=10_000)
    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=0)


class HintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=0)


class CloseSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1_000)


class ErrorBody(BaseModel):
    error: str
    message: str
    revision: int | None = None


class ForkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=200)


TERMINAL_STATUSES = {
    "agreement_reached",
    "walked_away",
    "expired",
    "aborted",
    "technical_failure",
}
