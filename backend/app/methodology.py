"""Versioned wording rules and deterministic, learner-only economic assessment."""

VERSION = "harvard-batna-voss-v1"
DIMENSIONS = {"economics", "process", "communication"}

NPC_INSTRUCTIONS = """
Apply the Harvard, BATNA/ZOPA, and Voss methodology within the selected engine action.
Keep the assigned role, difficulty, and conversation style.
Answer a direct question before asking another question.
Use only authorized facts in the answer.
If the answer is unavailable, state this briefly.
Separate the business issue from the person.
When useful, ask what need or constraint explains a stated position.
Use supplied objective criteria or ask for supporting evidence.
Do not invent market standards or past agreements.
Explain a conditional exchange only if the engine has selected that exchange.
Do not treat a low price alone as a mutually acceptable package.
Do not reveal private BATNA, reservation utility, or ZOPA limits.
You may discuss an explicitly disclosed alternative.
Do not invent an alternative or infer a private limit.
You may reflect a short phrase, summarize, or tentatively name a stated concern.
Present a concern as a question or a tentative interpretation, not a diagnosis.
When the selected action permits it, use at most one useful what or how question.
Do not repeat a listening technique mechanically.
Do not force a technique into every reply.
Do not mention methodology names in character.
Warm language does not authorize a concession, a fact, or an agreement.
"""

GROUNDING_INSTRUCTIONS = """
Check the Harvard, BATNA/ZOPA, and Voss wording rules.
Reject an evasive reply to a direct question when the authorized answer is available.
Reject invented objective criteria, past agreements, and economic limits.
Reject an exchange that the selected engine action does not authorize.
Reject a claim about the player's emotions or motives presented as a known fact.
A tentative interpretation of a stated concern is permitted.
Do not require a named technique or a concession.
"""

REVIEW_INSTRUCTIONS = """
Use methodology.economics as the authoritative economic assessment.
Produce exactly three cards, one for each dimension: economics, process, communication.
Each card must also contain dimension and assessment.
assessment must be observed or insufficient_evidence.
For economics, compare the outcome with the learner's BATNA and reservation utility.
These are different reference values.
Without agreement, the agreement margins are null.
Without agreement, participant_utility is the alternative utility.
It does not measure the utility of a rejected offer.
An empty offer_history does not mean that all available offers were unacceptable.
With no agreement and an empty offer_history, set the economics assessment to insufficient_evidence.
In this case, do not call the exit economically correct, rational, justified, or necessary.
This rule applies to summary, goal_assessment, and all cards.
Do not describe null as zero.
Do not classify every agreement as success or every exit as failure.
Do not infer an exact ZOPA or private NPC limits from the transcript.
For process, examine interests, supported objective criteria, options, and conditional exchanges.
For communication, examine listening, direct answers, and respectful firmness.
Voss techniques are optional: short reflection, tentative labels, summaries, and what or how questions.
Assess whether a technique fits the cited context.
Do not count technique names or phrases as proof of skill.
Use insufficient_evidence when the supplied record cannot support a conclusion.
Cite the message that shows this limit.
Insufficient evidence is not a failed skill.
Do not invent events to fill a dimension.
Suggest one specific practice step per dimension.
"""


def instructions(version: str, *, grounding: bool = False) -> str:
    if version not in {"", VERSION}:
        raise ValueError("Unknown negotiation methodology version")
    if not version:
        return ""
    return GROUNDING_INSTRUCTIONS if grounding else NPC_INSTRUCTIONS


def assess_economics(outcome: dict, baseline: dict) -> dict:
    """Use only the actor-safe outcome and the learner's own baseline."""
    agreement = outcome["agreement"]
    utility = outcome["participant_utility"]
    return {
        "version": VERSION,
        "economics": {
            "outcome": "agreement" if agreement else "no_agreement",
            "surplus_over_batna": round(utility - baseline["batna_utility"], 6) if agreement else None,
            "margin_over_reservation": round(utility - baseline["reservation_utility"], 6) if agreement else None,
            "meets_reservation": utility >= baseline["reservation_utility"] if agreement else None,
        },
        "zopa": "not_inferred",
    }
