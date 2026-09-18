from __future__ import annotations

from contextlib import asynccontextmanager
import os
import secrets
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from clients.providers import QwenCloudProvider, provider_for

from .config import Settings
from .db import Database
from .dialogue import LlmNpcDialogueRenderer, NpcDialogueRenderer, TemplateNpcDialogueRenderer
from .models import (
    CloseSessionRequest,
    CreateSessionRequest,
    HintRequest,
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


def get_participant_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise AuthenticationError("A Bearer participant credential is required")
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.casefold() != "bearer" or not token:
        raise AuthenticationError("Authorization must use a Bearer participant credential")
    return token


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
        timeout=settings.npc_timeout_seconds,
    )
    return LlmNpcDialogueRenderer(text_provider)


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
        extractor = None
        if configured.supply_semantic_extraction:
            from .supply_extraction import LlmSupplyExtractor
            if not isinstance(renderer, LlmNpcDialogueRenderer):
                raise ValueError("Supply semantic extraction requires a configured LLM provider")
            extractor = LlmSupplyExtractor(renderer._text_provider)
        service = NegotiationService(
            database,
            dialogue_renderer=renderer,
            supply_extractor=extractor,
            known_redaction_secrets=(
                configured.admin_token,
                os.getenv(configured.npc_api_key_env, "") if configured.npc_api_key_env else "",
            ),
        )
        application.state.service = service
        application.state.recovered_npc_render_count = service.recover_pending_npc_renders()
        yield

    application = FastAPI(
        title="Negotiation Trainer API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    @router.get("/health")
    def health(request: Request) -> dict:
        database: Database = request.app.state.database
        negotiation_service: NegotiationService = request.app.state.service
        return {
            "status": "ok",
            "database": "sqlite",
            "journal_mode": database.journal_mode(),
            "scenario_count": len(negotiation_service.list_scenarios()),
        }

    @router.get("/scenarios")
    def list_scenarios(
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        language: str | None = None,
    ) -> dict:
        items = negotiation_service.list_scenarios(language)
        return {"items": items, "count": len(items)}

    @router.get("/scenarios/{scenario_id}")
    def get_scenario(
        scenario_id: str,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_scenario(scenario_id)

    @router.get("/scenarios/{scenario_id}/versions/{version}")
    def get_scenario_version(
        scenario_id: str,
        version: int,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_scenario(scenario_id, version)

    @router.post("/sessions", status_code=201)
    def create_session(
        body: CreateSessionRequest,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Header()] = None,
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

    @router.get("/sessions/{session_id}")
    def get_session(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_session(session_id, token)

    @router.get("/sessions/{session_id}/observation")
    def get_observation(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_observation(session_id, token)

    @router.post("/sessions/{session_id}/messages")
    def submit_message(
        session_id: str,
        body: SubmitMessageRequest,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(negotiation_service.submit_message(session_id, token, body))

    @router.get("/sessions/{session_id}/messages")
    def get_messages(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_messages(session_id, token)

    @router.get("/sessions/{session_id}/events")
    def get_events(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_events(session_id, token)

    @router.get("/sessions/{session_id}/history")
    def get_history(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.get_history(session_id, token)

    @router.post("/sessions/{session_id}/hints")
    def request_hint(
        session_id: str,
        body: HintRequest,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(negotiation_service.request_hint(session_id, token, body))

    @router.get("/sessions/{session_id}/review")
    def get_review(
        session_id: str,
        token: Annotated[str, Depends(get_participant_token)],
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> JSONResponse:
        return _json_result(negotiation_service.get_review(session_id, token))

    @router.post("/sessions/{session_id}/close")
    def close_session(
        session_id: str,
        body: CloseSessionRequest,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        error = _administrator_error(
            authorization,
            configured.admin_token,
            disabled_error="administrative_close_disabled",
        )
        if error is not None:
            return error
        return _json_result(negotiation_service.close_session(session_id, body))

    @router.get("/admin/sessions")
    def list_admin_sessions(
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Header()] = None,
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

    @router.get("/admin/sessions/{session_id}")
    def get_admin_session(
        session_id: str,
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
        authorization: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        error = _administrator_error(authorization, configured.admin_token)
        if error is not None:
            return error
        return JSONResponse(content=negotiation_service.get_admin_session(session_id))

    @router.get("/stats")
    def stats(
        negotiation_service: Annotated[NegotiationService, Depends(get_service)],
    ) -> dict:
        return negotiation_service.aggregate_stats()

    application.include_router(router, prefix="/api/v1")
    application.include_router(router, include_in_schema=False)
    return application


app = create_app()
