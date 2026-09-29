"""Synthetic contract fixtures. These do not represent a live model assessment."""

from backend.app.behavior import CRITERIA


def behavior_fixture():
    return {"summary": "Недостаточно контекста для полного вывода о действиях.", "criteria": [
        {"criterion": criterion, "assessment": "insufficient_evidence", "evidence_refs": [],
         "observation": "Для этого критерия не хватает контекста.", "strength": None,
         "improvement": None, "alternative_phrase": None, "next_practice": None}
        for criterion in CRITERIA
    ]}
