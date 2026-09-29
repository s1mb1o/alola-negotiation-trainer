"""Evidence-linked player actions. No authority over economic or social state."""

from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION = "player-behavior-v1"
Criterion = Literal[
    "rapport", "listening", "interest_discovery", "argumentation",
    "conditional_trading", "clarity", "plan_adherence",
]
CRITERIA = get_args(Criterion)
Assessment = Literal["effective", "needs_improvement", "mixed", "insufficient_evidence"]
Text = Annotated[str, Field(min_length=1, max_length=600)]

INSTRUCTIONS = """
Also return behavior with exactly these keys: summary, criteria.
Limit the behavior summary to 600 characters.
Include exactly seven criteria, in this order:
rapport: Assess context-appropriate contact and respectful conduct.
listening: Assess questions, direct answers, and use of the counterpart's replies.
interest_discovery: Assess discovery of needs, priorities, and constraints.
argumentation: Assess reasons and supported objective criteria.
conditional_trading: Assess reciprocal concessions and conditional exchanges.
clarity: Assess clear proposals, summaries, and agreement checks.
plan_adherence: Compare actions with the private preparation, including discovery questions and possible trades.
Each criterion must contain exactly these keys:
criterion, assessment, evidence_refs, observation, strength, improvement, alternative_phrase, next_practice.
assessment must be effective, needs_improvement, mixed, or insufficient_evidence.
Use mixed when the cited actions include both a strength and an improvement.
Limit every text field to 600 characters. Prefer one short sentence per field.
Each observed assessment must cite one to three valid evidence references.
At least one cited reference must be a player message.
Select this reference by is_player=true, not by its position in the conversation.
For listening, cite the player's response as well as any NPC context you need.
NPC messages may supply context but cannot establish a player action alone.
effective requires a strength. Do not invent a weakness for balance.
Describe the observable action in strength, not a guaranteed effect of that action.
needs_improvement requires an improvement, alternative_phrase, and next_practice.
mixed requires all four advice fields.
For insufficient_evidence, explain the evidence limit in observation.
Set all four advice fields to null for insufficient_evidence.
For insufficient_evidence, evidence_refs may be empty if no relevant message exists.
Use null for other advice fields that do not apply.
If private preparation is empty, plan_adherence must be insufficient_evidence.
Assess actions, not personality, intelligence, motives, or psychological traits.
A favorable deal does not prove effective behavior. No agreement does not prove ineffective behavior.
Do not require small talk. Do not penalize concise or culturally different communication alone.
Do not reward a technique name or a personal-interest question alone.
Judge personal interest by the available context and observed replies.
Distinguish initial familiarity from conduct in this session.
Do not infer causality from message order, a polite reply, or a simulated social value.
Plan adaptation can be appropriate. Do not reward rigid adherence automatically.
Do not blame the player for parser or NPC limitations without evidence of a player action.
Do not mark an already explicit conditional exchange as missing merely because it uses different words.
Do not require a question when the counterpart has already supplied the relevant information.
When supplied messages support a narrow observation, assess that observation instead of using a generic evidence-limit sentence.
For insufficient_evidence, identify the specific missing information or observable exchange.
Do not require a named technique or a fixed phrase format in practice tasks.
Do not invent a number or total score for behavior.
Keep economic and behavioral conclusions separate.
Alternatives are hypotheses, not observed or guaranteed effects.
"""

GROUNDING = """
Check every behavior criterion against the cited player actions and available context.
Reject a favorable behavior rating justified only by a favorable deal or polite NPC response.
Reject a negative behavior rating justified only by no agreement.
Reject inferred personality, motives, emotions, or guaranteed causal effects.
Reject automatic rewards for personal questions, named techniques, or initial familiarity.
Do not require small talk or a particular communication style.
Reject missing evidence presented as a weakness.
Check plan_adherence against private preparation, not only final terms.
Permit justified plan adaptation. Do not assume that rigid adherence is effective.
Do not attribute system limitations to the player without evidence.
Require strength and improvement claims to match the cited actions.
Apply the same checks to behavior.summary and the overall summary.
"""


class BehaviorItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    criterion: Criterion
    assessment: Assessment
    evidence_refs: list[str] = Field(max_length=3)
    observation: Text
    strength: Text | None = None
    improvement: Text | None = None
    alternative_phrase: Text | None = None
    next_practice: Text | None = None

    @model_validator(mode="after")
    def validate_assessment(self):
        advice = (self.strength, self.improvement, self.alternative_phrase, self.next_practice)
        if self.assessment == "insufficient_evidence":
            if any(value is not None for value in advice):
                raise ValueError("Missing evidence cannot establish strengths or improvements")
        else:
            if not self.evidence_refs:
                raise ValueError("Observed behavior requires evidence")
            if self.assessment in {"effective", "mixed"} and self.strength is None:
                raise ValueError("A positive assessment requires a strength")
            if self.assessment in {"needs_improvement", "mixed"} and any(value is None for value in advice[1:]):
                raise ValueError("An improvement requires an alternative and practice")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("Duplicate behavior evidence")
        return self


class BehaviorReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: Text
    criteria: list[BehaviorItem] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_criteria(self):
        if {item.criterion for item in self.criteria} != set(CRITERIA):
            raise ValueError("Behavior requires seven distinct criteria")
        return self


def validate_evidence(behavior: dict, package: dict) -> None:
    by_ref = {item["ref"]: item for item in package["evidence"]}
    preparation = package.get("preparation", {})
    has_plan = any(str(preparation.get(key, "")).strip() for key in (
        "target", "unacceptable_result", "available_trades", "information_to_discover"
    )) or bool(preparation.get("targets"))
    for item in behavior["criteria"]:
        if any(ref not in by_ref for ref in item["evidence_refs"]):
            raise ValueError("Unknown behavior evidence")
        if item["assessment"] != "insufficient_evidence":
            if not any(by_ref[ref].get("is_player") is True for ref in item["evidence_refs"]):
                raise ValueError("Observed behavior requires a player message")
            if item["criterion"] == "plan_adherence" and not has_plan:
                raise ValueError("Plan adherence requires private preparation")
