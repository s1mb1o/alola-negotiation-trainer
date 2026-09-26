"""Route documentation and synthetic examples for the generated OpenAPI document."""

from copy import deepcopy

from .api_contracts import ApiError, PendingCoaching, ValidationErrorResponse

PARTICIPANT = (
    "Requires a session-scoped participant Bearer credential. Returns only the authenticated "
    "actor's permitted projection. Never returns counterpart private state. "
)
ADMIN = (
    "Requires the administrator Bearer credential configured by NEGOTIATION_ADMIN_TOKEN. "
    "Participant credentials do not grant this access. Returns 503 when admin access is disabled. "
)
MUTATION = (
    "Use a new idempotency_key for each new command. Reuse the same key and identical body "
    "to retry a command. Reusing a key with a different body returns 409. "
    "expected_revision must match the current session revision. Conflicts return 409. "
    "A rejected protocol action can still advance revision; read the returned revision. "
)
REVIEW = (
    "Requires a terminal session. Benchmark results remain sealed until the complete declared "
    "run set is terminal. Unavailable or sealed reviews return 409. "
)

ERROR_DESCRIPTIONS = {
    401: "Missing, invalid, or wrong-actor Bearer credential.",
    404: "Scenario, session, review, or requested checkpoint was not found.",
    409: "Revision, idempotency, turn, lifecycle, or disclosure conflict. Inspect error and revision.",
    422: "Request validation failed or the command violates the scenario contract.",
    503: "Administrative access is disabled because no administrator credential is configured.",
}
ERROR_EXAMPLES = {
    401: {
        "error": "participant_unauthorized",
        "message": "A Bearer participant credential is required",
    },
    404: {"error": "not_found", "message": "Session was not found"},
    409: {
        "error": "revision_conflict",
        "message": "expected_revision does not match the session revision",
        "revision": 2,
    },
    422: {
        "detail": [
            {
                "type": "missing",
                "loc": ["body", "idempotency_key"],
                "msg": "Field required",
                "input": {},
            }
        ]
    },
    503: {
        "error": "administrative_access_disabled",
        "message": "NEGOTIATION_ADMIN_TOKEN is not configured",
    },
}

# These fixtures are authored examples, never exports of a real session.
OBSERVATION_EXAMPLE = {
    "participant_id": "participant_demo_buyer",
    "role": "buyer",
    "role_brief": {
        "summary": "Вы представляете учебную компанию.",
        "objectives": [],
        "context": "Учебные переговоры.",
        "batna": "",
        "constraints": {},
        "priorities": [],
    },
    "currency": "RUB",
    "conversation": [],
    "active_offers": [],
    "assistance": None,
    "hints": [],
    "remaining_hints": 3,
    "hints_available": True,
    "context": [],
    "status": "active",
    "revision": 0,
    "round": 1,
    "substantive_turn_count": 0,
    "next_actor": "participant_demo_buyer",
    "language": "ru",
}
MESSAGE_EXAMPLE = {
    "result": "turn_committed",
    "session_id": "sess_demo",
    "round": 1,
    "substantive_turn_count": 2,
    "revision": 2,
    "status": "active",
    "next_actor": "participant_demo_buyer",
    "committed_actions": [],
    "observation": {**OBSERVATION_EXAMPLE, "revision": 2, "substantive_turn_count": 2},
}


def document(
    operation_id,
    model,
    summary,
    description,
    *,
    tag="Player",
    errors=(),
    status_code=200,
    example=None,
    pending=False,
):
    """Build FastAPI route metadata. Runtime checks remain in the route and service."""
    responses = {}
    for status in errors:
        error_example = ERROR_EXAMPLES[status]
        if status == 401 and (tag == "Administration" or operation_id == "createSession"):
            error_example = {
                "error": "administrator_unauthorized",
                "message": "A valid administrator Bearer credential is required",
            }
        elif status == 404 and operation_id in {
            "getScenario",
            "getScenarioVersion",
            "createSession",
        }:
            error_example = {
                "error": "scenario_not_found" if operation_id == "createSession" else "not_found",
                "message": "Scenario version was not found",
            }
        elif status == 409 and operation_id in {"getReview", "requestCoaching", "compareTraining"}:
            error_example = {
                "error": "review_not_ready",
                "message": "A review is available only after session termination",
                "revision": 0,
            }
        elif status == 409 and operation_id == "listCheckpoints":
            error_example = {"error": "training_not_available", "message": "training not available"}
        elif status == 409 and operation_id in {"createSession", "forkSession"}:
            error_example = {
                "error": "idempotency_key_reused",
                "message": "The idempotency key was already used with a different request",
            }
        elif status == 503 and operation_id == "closeSession":
            error_example = {
                "error": "administrative_close_disabled",
                "message": "NEGOTIATION_ADMIN_TOKEN is not configured",
            }
        responses[status] = {
            "model": ApiError | ValidationErrorResponse if status == 422 else ApiError,
            "description": ERROR_DESCRIPTIONS[status],
            "content": {"application/json": {"example": error_example}},
        }
        if status == 401:
            responses[status]["headers"] = {
                "WWW-Authenticate": {"schema": {"type": "string"}, "example": "Bearer"}
            }
    if example is not None:
        responses[status_code] = {"content": {"application/json": {"example": example}}}
    if pending:
        responses[202] = {
            "model": PendingCoaching,
            "description": "Coaching is already in progress. Retry this request later.",
            "content": {"application/json": {"example": {"status": "pending"}}},
        }
    return {
        "operation_id": operation_id,
        "response_model": model,
        "response_model_exclude_unset": True,
        "summary": summary,
        "description": description,
        "tags": [tag],
        "responses": responses,
        "status_code": status_code,
    }


def preserve_response_examples(application, router):
    """Preserve explicit nulls that FastAPI's OpenAPI serialization otherwise removes."""
    generate = application.openapi

    def openapi():
        if application.openapi_schema is None:
            schema = generate()
            routes = {route.operation_id: route for route in router.routes}
            for methods in schema["paths"].values():
                for operation in methods.values():
                    route = routes[operation["operationId"]]
                    for status, response in route.responses.items():
                        for media_type, media in response.get("content", {}).items():
                            target = operation["responses"][str(status)]["content"][media_type]
                            for key in ("example", "examples"):
                                if key in media:
                                    target[key] = deepcopy(media[key])
        return application.openapi_schema

    application.openapi = openapi
