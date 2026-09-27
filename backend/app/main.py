from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from copy import copy
from ipaddress import ip_address
import os
from pathlib import Path
import re
import secrets
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from clients.providers import QwenCloudProvider, provider_for

from . import api_contracts as contracts
from .api_documentation import (
    ADMIN,
    MUTATION,
    PARTICIPANT,
    REVIEW,
    MESSAGE_EXAMPLE,
    OBSERVATION_EXAMPLE,
    document,
    preserve_response_examples,
)
from .config import Settings
from .db import Database
from .llm_trace import LlmTraceRecorder, TracedProvider, trace_session
from .dialogue import LlmNpcDialogueRenderer, NpcDialogueRenderer, TemplateNpcDialogueRenderer
from .models import (
    AssistedReplyRequest,
    CloseSessionRequest,
    CreateSessionRequest,
    HintRequest,
    ForkRequest,
    RunMode,
    SubmitMessageRequest,
)
from .scenarios import ScenarioCatalog
from .service import (
    AuthenticationError,
    MissingResourceError,
    NegotiationService,
    ServiceResult,
)


def _json_result(result: ServiceResult) -> JSONResponse:
    return JSONResponse(status_code=result.status_code, content=result.payload)


def get_service(request: Request) -> NegotiationService:
    return request.app.state.service


participant_bearer = HTTPBearer(
    scheme_name="ParticipantBearer",
    auto_error=False,
    description="Session-scoped participant token returned once by session creation or fork. "
    "Use only for that participant's session. This is not a provider API key.",
)
administrator_bearer = HTTPBearer(
    scheme_name="AdministratorBearer",
    auto_error=False,
    description="Administrator credential configured by NEGOTIATION_ADMIN_TOKEN. "
    "Participant tokens and LLM provider keys do not grant this access.",
)


def get_participant_token(
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
    _credential: Annotated[
        HTTPAuthorizationCredentials | None, Security(participant_bearer)
    ] = None,
) -> str:
    if not authorization:
        raise AuthenticationError("A Bearer participant credential is required")
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.casefold() != "bearer" or not token:
        raise AuthenticationError("Authorization must use a Bearer participant credential")
    return token


def get_admin_authorization(
    request: Request,
    _credential: Annotated[
        HTTPAuthorizationCredentials | None, Security(administrator_bearer)
    ] = None,
) -> str | None:
    # Preserve existing authentication errors, including the disabled-admin 503 response.
    return request.headers.get("Authorization")


def _administrator_error(
    authorization: str | None,
    configured_token: str,
    *,
    disabled_error: str = "administrative_access_disabled",
    disabled_message: str = "NEGOTIATION_ADMIN_TOKEN is not configured",
) -> JSONResponse | None:
    if not configured_token:
        return JSONResponse(
            status_code=503,
            content={"error": disabled_error, "message": disabled_message},
        )
    scheme, separator, token = (authorization or "").partition(" ")
    if (
        separator != " "
        or scheme.casefold() != "bearer"
        or not secrets.compare_digest(token.encode("utf-8"), configured_token.encode("utf-8"))
    ):
        return JSONResponse(
            status_code=401,
            content={
                "error": "administrator_unauthorized",
                "message": "A valid administrator Bearer credential is required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None


def _local_trace_request(request: Request) -> bool:
    """Allow the local diagnostics window without granting access to other APIs."""
    if request.client is None:
        return False
    try:
        if not ip_address(request.client.host).is_loopback:
            return False
        host = request.url.hostname or ""
        if host != "localhost" and not ip_address(host).is_loopback:
            return False
    except ValueError:
        return False
    origin = request.headers.get("origin")
    return origin is None or origin == str(request.base_url).rstrip("/")


def _configured_dialogue_renderer(settings: Settings) -> NpcDialogueRenderer:
    if settings.npc_provider == "template":
        return TemplateNpcDialogueRenderer()
    base_url = settings.npc_base_url
    model = settings.npc_model
    if settings.npc_provider == "qwen" and base_url is None:
        base_url = QwenCloudProvider.TOKEN_PLAN_BASE_URL
    if settings.npc_provider == "qwen" and model is None:
        model = "qwen3.8-max"
    text_provider = provider_for(
        settings.npc_provider,
        model=model,
        api_key_env=settings.npc_api_key_env,
        base_url=base_url,
        max_output_tokens=settings.npc_max_output_tokens,
        temperature=settings.npc_temperature,
        enable_thinking=settings.npc_enable_thinking,
        timeout=settings.npc_timeout_seconds,
    )
    control_provider = _configured_task_provider(settings, "control", text_provider)
    return LlmNpcDialogueRenderer(
        text_provider,
        grounding_provider=control_provider or text_provider,
    )


def _configured_task_provider(settings: Settings, task: str, fallback):
    provider_name = getattr(settings, f"{task}_provider")
    model = getattr(settings, f"{task}_model")
    api_key_env = getattr(settings, f"{task}_api_key_env")
    base_url = getattr(settings, f"{task}_base_url")
    temperature = getattr(settings, f"{task}_temperature")
    enable_thinking = getattr(settings, f"{task}_enable_thinking")
    timeout = getattr(settings, f"{task}_timeout_seconds")
    default_timeout = 20.0 if task == "control" else 45.0
    if not any((provider_name, model, api_key_env, base_url, temperature is not None,
                enable_thinking is not None, timeout != default_timeout)):
        return fallback
    fallback_config = getattr(fallback, "config", None)
    fallback_provider = getattr(fallback_config, "provider", None)
    provider_name = provider_name or fallback_provider
    if provider_name in {None, "template"}:
        return None
    same_provider = provider_name == fallback_provider
    model = model or (getattr(fallback_config, "model", None) if same_provider else None)
    api_key_env = api_key_env or (
        getattr(fallback_config, "api_key_env", None) if same_provider else None
    )
    base_url = base_url or (
        getattr(fallback_config, "base_url", None) if same_provider else None
    )
    return provider_for(
        provider_name,
        model=model,
        api_key_env=api_key_env,
        base_url=base_url,
        max_output_tokens=getattr(fallback_config, "max_output_tokens", 500),
        temperature=temperature,
        enable_thinking=enable_thinking,
        timeout=timeout,
    )


def _bounded_provider(provider, max_output_tokens):
    if provider is None or not hasattr(provider, "config"):
        return None
    bounded = copy(provider)
    bounded.config = replace(
        provider.config,
        max_output_tokens=max_output_tokens,
        max_attempts=1,
        timeout=min(provider.config.timeout, 45.0),
    )
    return bounded


def create_app(
    settings: Settings | None = None,
    *,
    npc_dialogue_renderer: NpcDialogueRenderer | None = None,
) -> FastAPI:
    configured = settings or Settings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        catalog = ScenarioCatalog(
            configured.scenario_directories,
            configured.scenario_schema_path,
        )
        database = Database(configured.database_path)
        database.initialize(catalog.discover())
        application.state.database = database
        renderer = npc_dialogue_renderer or _configured_dialogue_renderer(configured)
        original_dialogue_provider = getattr(renderer, "_text_provider", None)
        original_control_provider = getattr(
            renderer, "_grounding_provider", original_dialogue_provider
        )
        original_review_provider = _configured_task_provider(
            configured, "review", original_control_provider
        )
        social_provider = _bounded_provider(original_control_provider, 350)
        review_provider = _bounded_provider(original_review_provider, 2200)
        player_assist_provider = _bounded_provider(original_review_provider, 700)
        recorder = LlmTraceRecorder(
            enabled=configured.llm_trace_enabled,
            secrets=(configured.admin_token,),
        )
        application.state.llm_traces = recorder
        if recorder.enabled and original_dialogue_provider is not None:
            renderer = copy(renderer)
            renderer._text_provider = TracedProvider(
                original_dialogue_provider, recorder, "npc_dialogue"
            )
            renderer._grounding_provider = TracedProvider(
                original_control_provider, recorder, "npc_grounding"
            )
            social_provider = TracedProvider(social_provider, recorder, "social") if social_provider else None
            review_provider = TracedProvider(review_provider, recorder, "coaching") if review_provider else None
            player_assist_provider = (
                TracedProvider(player_assist_provider, recorder, "player_assist")
                if player_assist_provider
                else None
            )
        extractor = None
        if configured.supply_semantic_extraction:
            from .supply_extraction import LlmSupplyExtractor

            if not isinstance(renderer, LlmNpcDialogueRenderer):
                raise ValueError("Supply semantic extraction requires a configured LLM provider")
            extraction_provider = (
                TracedProvider(original_control_provider, recorder, "supply_extraction")
                if recorder.enabled else original_control_provider
            )
            extractor = LlmSupplyExtractor(extraction_provider)
        service = NegotiationService(
            database,
            dialogue_renderer=renderer,
            supply_extractor=extractor,
            social_provider=social_provider,
            review_provider=review_provider,
            player_assist_provider=player_assist_provider,
            known_redaction_secrets=(
                configured.admin_token,
                os.getenv(configured.npc_api_key_env, "") if configured.npc_api_key_env else "",
                os.getenv(configured.control_api_key_env, "")
                if configured.control_api_key_env else "",
                os.getenv(configured.review_api_key_env, "")
                if configured.review_api_key_env else "",
            ),
        )
        application.state.service = service
        application.state.recovered_npc_render_count = service.recover_pending_npc_renders()
        yield

    application = FastAPI(
        title="Negotiation Trainer API",
        version="0.1.0",
        description="API-first negotiation training. Session dialogue uses the requested language "
        "(Russian for the MVP). Canonical routes use /api/v1. "
        "Authorize with a participant or administrator credential, never an LLM API key. "
        "Public schemas describe permitted projections, not internal negotiation state.",
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_parameters={"persistAuthorization": False},
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def trace_training_session(request: Request, call_next):
        session_id = None
        match = re.fullmatch(r"(?:/api/v1)?/sessions/(sess_[a-zA-Z0-9]+)/[a-z-]+", request.url.path)
        if configured.llm_trace_enabled and match and hasattr(application.state, "database"):
            with application.state.database.read_connection() as connection:
                row = connection.execute("SELECT run_mode FROM sessions WHERE id = ?", (match[1],)).fetchone()
            if row and row["run_mode"] == "training":
                session_id = match[1]
        token = trace_session.set(session_id)
        try:
            response = await call_next(request)
            if "/admin/llm-traces" in request.url.path or request.url.path.startswith("/llm-debug"):
                response.headers["Cache-Control"] = "no-store"
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["Referrer-Policy"] = "no-referrer"
            return response
        finally:
            trace_session.reset(token)

    @application.get("/llm-debug", include_in_schema=False)
    def llm_debug_page():
        return FileResponse(Path(__file__).with_name("static") / "llm-debug.html", headers={
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        })

    @application.get("/llm-debug/{asset}", include_in_schema=False)
    def llm_debug_asset(asset: str):
        if asset not in {"llm-debug.js", "llm-debug.css"}:
            return JSONResponse(status_code=404, content={"error": "not_found", "message": "Asset not found"})
        return FileResponse(Path(__file__).with_name("static") / asset)

    @application.exception_handler(AuthenticationError)
    async def authentication_error(_request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": "participant_unauthorized", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @application.exception_handler(MissingResourceError)
    async def missing_resource(_request: Request, exc: MissingResourceError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": str(exc)},
        )

    router = APIRouter()

    @router.get("/admin/llm-traces", openapi_extra={"security": [{}]}, **document(
        "listLlmTraces", contracts.LlmTraceListResponse, "List recent LLM calls",
        "Local loopback clients using a loopback host may read without a credential. "
        "A supplied Origin must match this API origin for local access. Other requests require AdministratorBearer. "
        "Returns bounded in-memory diagnostics for training sessions. "
        "Requires NEGOTIATION_LLM_TRACE=true to capture new calls. Excludes benchmarks. "
        "Records disappear on restart. A completed call can still fail dialogue validation.",
        tag="Administration", errors=(401, 422, 503),
    ))
    def list_llm_traces(
        request: Request,
        session_id: Annotated[str | None, Query(max_length=100)] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
        authorization: Annotated[str | None, Depends(get_admin_authorization)] = None,
    ):
        error = None if _local_trace_request(request) else _administrator_error(authorization, configured.admin_token)
        if error:
            return error
        return application.state.llm_traces.list(session_id=session_id, limit=limit)

    @router.get("/admin/llm-traces/{trace_id}", openapi_extra={"security": [{}]}, **document(
        "getLlmTrace", contracts.LlmTraceDetail, "Inspect one LLM call",
        "Local loopback clients using a loopback host may read without a credential. "
        "A supplied Origin must match this API origin for local access. Other requests require AdministratorBearer. "
        "Returns complete redacted instructions, input, response text, telemetry, and outgoing request attempts. "
        "Each request includes the resolved URL, redacted headers, complete JSON body, and timeout. "
        "This privileged content can include NPC context. It is never a Player API projection. "
        "Missing or evicted records return 404. Records are evicted whole without content truncation.",
        tag="Administration", errors=(401, 404, 422, 503),
    ))
    def get_llm_trace(
        trace_id: str,
        request: Request,
        authorization: Annotated[str | None, Depends(get_admin_authorization)] = None,
    ):
        error = None if _local_trace_request(request) else _administrator_error(authorization, configured.admin_token)
        if error:
            return error
        record = application.state.llm_traces.get(trace_id)
        if record is None:
            return JSONResponse(status_code=404, content={"error": "not_found", "message": "LLM call not found"})
        return record

    @router.get(
        "/health",
        **document(
            "getHealth",
            contracts.HealthResponse,
            "Check service health",
            "Public database and scenario-catalog health. Does not call a model.",
            tag="Public",
            example={
                "status": "ok",
                "database": "sqlite",
                "journal_mode": "wal",
                "scenario_count": 9,
            },
        ),
    )
    def health(request: Request) -> dict:
        database: Database = request.app.state.database
        negotiation_service: NegotiationService = request.app.state.service
        return {
            "status": "ok",
            "database": "sqlite",
            "journal_mode": database.journal_mode(),
            "scenario_count": len(negotiation_service.list_scenarios()),
        }

    @router.get(
        "/scenarios",
        **document(
            "listScenarios",
            contracts.ScenarioListResponse,
            "List published scenarios",
            "Public metadata for the latest version of each scenario. "
            "Optional language filter. Excludes private role economics and raw scenario source.",
            tag="Public",
            errors=(422,),
            example={"items": [], "count": 0},
        ),
    )
    def list_scenarios(
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        language: str | None = None,
    ) -> dict:
        items = negotiation_service.list_scenarios(language)
        return {"items": items, "count": len(items)}

    @router.get(
        "/scenarios/{scenario_id}",
        **document(
            "getScenario",
            contracts.ScenarioResponse,
            "Get latest scenario metadata",
            "Public metadata for one scenario's latest immutable version. "
            "Excludes private role economics and raw scenario source.",
            tag="Public",
            errors=(404, 422),
        ),
    )
    def get_scenario(
        scenario_id: str,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_scenario(scenario_id)

    @router.get(
        "/scenarios/{scenario_id}/versions/{version}",
        **document(
            "getScenarioVersion",
            contracts.ScenarioResponse,
            "Get pinned scenario metadata",
            "Public metadata for one exact "
            "immutable scenario version. Excludes private role economics and raw scenario source.",
            tag="Public",
            errors=(404, 422),
        ),
    )
    def get_scenario_version(
        scenario_id: str,
        version: int,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_scenario(scenario_id, version)

    @router.post(
        "/sessions",
        openapi_extra={"security": [{}]},
        **document(
            "createSession",
            contracts.CreateSessionResponse,
            "Create a negotiation session",
            "Training creation is public. Benchmark creation requires AdministratorBearer when "
            "NEGOTIATION_ADMIN_TOKEN is configured; otherwise it is public. The optional OpenAPI "
            "security alternative represents training access, not permission to bypass the benchmark gate. "
            "Pin scenario version and language. Use a new idempotency_key for a new session. "
            "Identical retries return the original result without participant_token or participant_credentials; "
            "credential_delivery becomes initial_response_only. Different bodies with the same key return 409. "
            "Save credentials from the first response privately. The initial observation belongs to the "
            "first non-NPC participant. Each participant must fetch its own authenticated observation.",
            errors=(401, 404, 409, 422),
            status_code=201,
        ),
    )
    def create_session(
        body: CreateSessionRequest,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Depends(get_admin_authorization)] = None,
    ) -> JSONResponse:
        if body.run_mode == RunMode.benchmark and configured.admin_token:
            # A benchmark run set is released only when every declared trial is terminal.
            # Without this gate any client could add a session to a run id and re-seal it.
            error = _administrator_error(
                authorization,
                configured.admin_token,
                disabled_error="benchmark_session_creation_disabled",
            )
            if error is not None:
                return error
        return _json_result(negotiation_service.create_session(body))

    @router.get(
        "/sessions/{session_id}",
        **document(
            "getSession",
            contracts.SessionResponse,
            "Get session state",
            PARTICIPANT + "Pending confirmation is visible only to its owner. "
            "Private preparation is visible only to the learner who owns it.",
            errors=(401, 404, 422),
        ),
    )
    def get_session(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_session(session_id, token)

    @router.get(
        "/sessions/{session_id}/observation",
        **document(
            "getObservation",
            contracts.Observation,
            "Get participant observation",
            PARTICIPANT + "Includes role brief, public conversation, "
            "offers, and permitted assistance. An omitted deal term remains unresolved.",
            errors=(401, 404, 422),
            example=OBSERVATION_EXAMPLE,
        ),
    )
    def get_observation(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_observation(session_id, token)

    @router.post(
        "/sessions/{session_id}/messages",
        **document(
            "submitMessage",
            contracts.MessageResponse,
            "Submit a natural-language message",
            PARTICIPANT
            + MUTATION
            + "Only next_actor may submit. The engine validates the parsed action. Acceptance intent "
            "does not bind a deal. A separate confirmation must identify the complete pending offer revision. "
            "Supply scenarios also require separate confirmation before offer publication. "
            "A successful response includes the committed NPC reply when applicable. While that reply "
            "is pending, concurrent commands return 409 npc_render_pending.",
            errors=(401, 404, 409, 422),
            example=MESSAGE_EXAMPLE,
        ),
    )
    def submit_message(
        session_id: str,
        body: SubmitMessageRequest,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(negotiation_service.submit_message(session_id, token, body))

    @router.get(
        "/sessions/{session_id}/messages",
        **document(
            "getMessages",
            contracts.MessagesResponse,
            "Get session transcript",
            PARTICIPANT + "Returns the ordered delivered transcript.",
            errors=(401, 404, 422),
            example={"session_id": "sess_demo", "revision": 0, "messages": []},
        ),
    )
    def get_messages(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_messages(session_id, token)

    @router.get(
        "/sessions/{session_id}/events",
        **document(
            "getEvents",
            contracts.EventsResponse,
            "Get participant events",
            PARTICIPANT + "Returns ordered public event payloads. "
            "Audience-specific events are visible only to their intended participant.",
            errors=(401, 404, 422),
            example={"session_id": "sess_demo", "revision": 0, "events": []},
        ),
    )
    def get_events(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_events(session_id, token)

    @router.get(
        "/sessions/{session_id}/history",
        **document(
            "getHistory",
            contracts.HistoryResponse,
            "Get transcript and event history",
            PARTICIPANT + "Returns transcript and actor-filtered "
            "events from one database read. Internal event payloads are excluded.",
            errors=(401, 404, 422),
            example={"session_id": "sess_demo", "revision": 0, "messages": [], "events": []},
        ),
    )
    def get_history(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_history(session_id, token)

    @router.post(
        "/sessions/{session_id}/hints",
        **document(
            "requestHint",
            contracts.HintResponse,
            "Request a training hint",
            PARTICIPANT + MUTATION + "Requires an active training session, "
            "enabled hints, the participant's turn, and remaining hint budget. Hints are private to "
            "their recipient. Benchmark sessions cannot request hints.",
            errors=(401, 404, 409, 422),
        ),
    )
    def request_hint(
        session_id: str,
        body: HintRequest,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(negotiation_service.request_hint(session_id, token, body))

    @router.post(
        "/sessions/{session_id}/player-assist",
        **document(
            "requestPlayerAssist",
            contracts.AssistedReplyResponse,
            "Generate the player's next message",
            PARTICIPANT + MUTATION + "Only the owner of an active human training "
            "session can request a player-side reply. The request requires the player's turn and the "
            "exact current revision. The provider receives only actor-safe state and the owner's private "
            "preparation. This operation does not mutate negotiation state. Submit the returned text "
            "through the normal message operation. Benchmark sessions cannot use this operation.",
            errors=(401, 404, 409, 422, 503),
        ),
    )
    def player_assist(
        session_id: str,
        body: AssistedReplyRequest,
        token: Annotated[str, Depends(get_participant_token)],
        service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(service.request_player_assist(session_id, token, body))

    @router.get(
        "/sessions/{session_id}/review",
        **document(
            "getReview",
            contracts.ReviewResponse,
            "Get final participant review",
            PARTICIPANT + REVIEW + "Returns the deterministic report "
            "and the owner's permitted training evidence. Training methodology includes the learner's "
            "agreement surplus over BATNA and margin over reservation utility. Without agreement, "
            "both margins are null. Does not initiate LLM coaching.",
            errors=(401, 404, 409, 422),
        ),
    )
    def get_review(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(negotiation_service.get_review(session_id, token))

    @router.post(
        "/sessions/{session_id}/coaching",
        **document(
            "requestCoaching",
            contracts.CoachingResponse,
            "Request final goal coaching",
            PARTICIPANT + REVIEW + "Only the owner of an opt-in human "
            "training session can request coaching. The result is cached per session and source revision. "
            "New coaching has three evidence-linked dimensions: economics, process, and communication. "
            "Each dimension states observed or insufficient_evidence. Historical cached cards can omit these labels. "
            "No idempotency key or expected_revision is needed because the session is terminal. "
            "Repeated requests return the cached result, or 202 while another request is pending. "
            "Provider failure returns status unavailable with HTTP 200; the deterministic report remains available.",
            errors=(401, 404, 409, 422),
            pending=True,
            example={"status": "unavailable", "reason": "provider_not_configured"},
        ),
    )
    def coaching(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(service.request_coaching(session_id, token))

    @router.get(
        "/sessions/{session_id}/checkpoints",
        **document(
            "listCheckpoints",
            contracts.CheckpointsResponse,
            "List learner decision checkpoints",
            PARTICIPANT + "Only the opt-in human training owner "
            "can list checkpoints. A list entry exposes a revision, not its hidden snapshot.",
            errors=(401, 404, 409, 422),
            example={"session_id": "sess_demo", "checkpoints": [{"source_revision": 0}]},
        ),
    )
    def checkpoints(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(service.get_training_checkpoints(session_id, token))

    @router.post(
        "/sessions/{session_id}/rewind",
        **document(
            "rewindSession",
            contracts.ForkResponse,
            "Rewind to an NPC message",
            PARTICIPANT + "Only the owner of an active human training session can rewind. "
            "source_revision must identify both a stored built-in-NPC message and an exact checkpoint. "
            "The source session remains unchanged. The child restores the checkpoint with fresh "
            "credentials. One root lineage permits three rewinds. Idempotency replay does not consume "
            "another attempt and does not return credentials again.",
            errors=(401, 404, 409, 422),
            status_code=201,
        ),
    )
    def rewind_session(
        session_id: str,
        body: ForkRequest,
        token: Annotated[str, Depends(get_participant_token)],
        service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(service.rewind_training_session(session_id, token, body))

    @router.post(
        "/sessions/{session_id}/fork",
        **document(
            "forkSession",
            contracts.ForkResponse,
            "Retry a learner checkpoint",
            PARTICIPANT + "Requires completed opt-in human training and "
            "an existing source_revision checkpoint. The parent is immutable. The child restores that "
            "checkpoint with fresh credentials. No expected_revision is needed. Use a new idempotency_key "
            "for each new retry. Identical requests replay the child result without credentials; "
            "different bodies with the same key return 409. Benchmarks cannot fork into training.",
            errors=(401, 404, 409, 422),
            status_code=201,
        ),
    )
    def fork_session(
        session_id: str,
        body: ForkRequest,
        token: Annotated[str, Depends(get_participant_token)],
        service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(service.fork_training_session(session_id, token, body))

    @router.get(
        "/sessions/{session_id}/comparison",
        **document(
            "compareTraining",
            contracts.ComparisonResponse,
            "Compare retry and parent outcomes",
            PARTICIPANT + REVIEW + "Requires a completed training "
            "child owned by this learner and an available parent report. Returns same-role observed "
            "outcomes. Informed practice does not establish causal skill improvement.",
            errors=(401, 404, 409, 422),
        ),
    )
    def comparison(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(service.compare_training(session_id, token))

    @router.post(
        "/sessions/{session_id}/close",
        **document(
            "closeSession",
            contracts.CloseResponse,
            "Abort a session administratively",
            ADMIN + MUTATION + "Closes an active session and "
            "records the supplied reason. Does not bypass benchmark review sealing.",
            tag="Administration",
            errors=(401, 404, 409, 422, 503),
            example={
                "session_id": "sess_demo",
                "revision": 1,
                "status": "aborted",
                "next_actor": None,
                "terminal_reason": "Учебная сессия закрыта.",
            },
        ),
    )
    def close_session(
        session_id: str,
        body: CloseSessionRequest,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Depends(get_admin_authorization)] = None,
    ) -> JSONResponse:
        error = _administrator_error(
            authorization,
            configured.admin_token,
            disabled_error="administrative_close_disabled",
        )
        if error is not None:
            return error
        return _json_result(negotiation_service.close_session(session_id, body))

    @router.get(
        "/admin/sessions",
        **document(
            "listAdminSessions",
            contracts.AdminSessionsResponse,
            "List sessions for inspection",
            ADMIN + "Returns paginated public summaries with exact "
            "optional filters. Excludes credentials, private preparation, and private economics.",
            tag="Administration",
            errors=(401, 422, 503),
            example={"items": [], "total": 0, "limit": 50, "offset": 0},
        ),
    )
    def list_admin_sessions(
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Depends(get_admin_authorization)] = None,
        status: str | None = None,
        scenario_id: str | None = None,
        language: str | None = None,
        run_mode: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> JSONResponse:
        error = _administrator_error(authorization, configured.admin_token)
        if error is not None:
            return error
        return JSONResponse(
            content=negotiation_service.list_admin_sessions(
                status=status,
                scenario_id=scenario_id,
                language=language,
                run_mode=run_mode,
                limit=limit,
                offset=offset,
            )
        )

    @router.get(
        "/admin/sessions/{session_id}",
        **document(
            "getAdminSession",
            contracts.AdminSessionResponse,
            "Inspect a session",
            ADMIN + "Includes public messages, event payloads, offers, and dialogue "
            "diagnostics. Excludes credentials, private learner preparation, private event payloads, and "
            "counterpart economics. The public review remains null until its disclosure gate permits access.",
            tag="Administration",
            errors=(401, 404, 422, 503),
        ),
    )
    def get_admin_session(
        session_id: str,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Depends(get_admin_authorization)] = None,
    ) -> JSONResponse:
        error = _administrator_error(authorization, configured.admin_token)
        if error is not None:
            return error
        return JSONResponse(content=negotiation_service.get_admin_session(session_id))

    @router.get(
        "/stats",
        **document(
            "getStats",
            contracts.StatsResponse,
            "Get aggregate statistics",
            "Public aggregate counts. Raw utility is suppressed. Small completed groups suppress "
            "average scores. Benchmark outcomes remain sealed until the declared run set is terminal.",
            tag="Public",
        ),
    )
    def stats(
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.aggregate_stats()

    application.include_router(router, prefix="/api/v1")
    application.include_router(router, include_in_schema=False)
    preserve_response_examples(application, router)
    return application


app = create_app()
