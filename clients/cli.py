"""Command-line client for humans and external negotiation agents."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from .agent import NegotiationAgent, PROMPT_VERSION
from .api import (
    ApiError,
    DEFAULT_MAX_ATTEMPTS,
    NegotiationApiClient,
    redact_secrets,
    response_revision,
    response_status,
)
from .orchestrator import (
    ADMIN_TOKEN_ENV,
    AgentSeat,
    TERMINAL_STATUSES,
    actor_safe_protocol_result,
    extract_participant_credentials,
    extract_participant_roles,
    run_self_play,
)
from .providers import ProviderError, provider_for
from .transcript_playback import (
    load_markdown_transcript,
    render_player_markdown,
    run_transcript_playback,
)


# The interactive loop cannot recover from these; everything else keeps the loop running.
FATAL_HTTP_STATUSES = {401, 403, 404}


def _print_json(value: Any) -> None:
    print(json.dumps(redact_secrets(value), ensure_ascii=False, indent=2, sort_keys=True))


def _participant_token(env_name: str, created: Mapping[str, Any] | None, role: str) -> str:
    """Prefer the credential issued for this session; the environment token is a fallback."""

    if created is not None:
        token = extract_participant_credentials(created).get(role)
        if token:
            return token
    token = os.getenv(env_name)
    if token:
        if created is not None:
            print(
                f"note: the backend did not deliver a participant credential for role {role!r}; "
                f"using {env_name}",
                file=sys.stderr,
            )
        return token
    raise ApiError(
        f"No participant credential is available for role {role!r}. "
        f"Set {env_name} or use a backend credential-delivery integration."
    )


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1 (got {parsed})")
    return parsed


def _provider(args: argparse.Namespace, prefix: str = "", *, seed: int | None = None):
    def key(name: str):
        return getattr(args, f"{prefix}{name}")

    return provider_for(
        key("provider"),
        model=key("model"),
        api_key_env=key("api_key_env"),
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
        seed=seed,
        timeout=args.provider_timeout,
        max_attempts=getattr(args, "provider_max_attempts", DEFAULT_MAX_ATTEMPTS),
    )


def _create_training_session(
    api: NegotiationApiClient,
    args: argparse.Namespace,
    *,
    controller: str,
    provider: Any = None,
) -> dict[str, Any]:
    participant: dict[str, Any] = {"role": args.role, "controller": controller}
    if provider is not None:
        participant.update(
            provider=provider.config.provider,
            model=provider.config.model,
            prompt_version=PROMPT_VERSION,
        )
    training_options = {}
    if getattr(args, "training_file", None):
        training_options["training"] = json.loads(Path(args.training_file).read_text(encoding="utf-8"))
    return api.create_session(
        scenario_id=args.scenario,
        scenario_version=args.scenario_version,
        language=args.language,
        participants=[
            participant,
            {"role": args.other_role, "controller": "built_in_npc"},
        ],
        difficulty=args.difficulty,
        hints_enabled=not args.no_hints,
        run_mode="training",
        **training_options,
    )


def _refreshed_state(
    participant_api: NegotiationApiClient, session_id: str
) -> dict[str, Any] | None:
    try:
        return participant_api.get_session(session_id)
    except ApiError as exc:
        print(f"error: cannot refresh the session state: {exc}", file=sys.stderr)
        return None


def command_play(api: NegotiationApiClient, args: argparse.Namespace) -> int:
    created = _create_training_session(api, args, controller="human")
    session_id = str(created["session_id"])
    token = _participant_token(args.participant_token_env, created, args.role)
    participant_api = api.with_participant_token(token)
    if not args.plain and sys.stdin.isatty() and sys.stdout.isatty():
        from .tui import run_play_tui

        return run_play_tui(participant_api, session_id, debug=args.debug)
    return _play_existing_plain(participant_api, created, args.role, token)


def _play_existing_plain(participant_api, created, role=None, token=None):
    session_id = str(created["session_id"])
    role = role or created.get("observation", {}).get("role", "player")
    token = token or participant_api.participant_token
    current: Mapping[str, Any] = created
    _print_json(redact_secrets(created, (token,)))
    while response_status(current) not in TERMINAL_STATUSES:
        try:
            message = input(f"{role}> ").strip()
        except EOFError:
            print()
            return 0
        if not message:
            continue
        if message in {"/quit", "/exit"}:
            return 0
        try:
            current = participant_api.submit_message(
                session_id,
                message,
                expected_revision=response_revision(current),
            )
        except ApiError as exc:
            if exc.status in FATAL_HTTP_STATUSES:
                raise
            # A domain error, a revision conflict, or a transport failure keeps the loop;
            # the refreshed state carries the current revision for the next message.
            print(f"error: {exc}", file=sys.stderr)
            refreshed = _refreshed_state(participant_api, session_id)
            if refreshed is not None:
                current = refreshed
            continue
        _print_json(redact_secrets(current, (token,)))
    _print_json(participant_api.review(session_id))
    return 0


def command_agent(api: NegotiationApiClient, args: argparse.Namespace) -> int:
    provider = _provider(args)
    created = _create_training_session(api, args, controller="external_agent", provider=provider)
    session_id = str(created["session_id"])
    token = _participant_token(args.participant_token_env, created, args.role)
    participant_api = api.with_participant_token(token)
    agent = NegotiationAgent(provider, role=args.role, language=args.language)
    current: Mapping[str, Any] = created
    participant_roles = extract_participant_roles(created)
    turns: list[dict[str, Any]] = []
    for step in range(1, args.max_messages + 1):
        status = response_status(current)
        if status in TERMINAL_STATUSES:
            break
        next_actor = current.get("next_actor")
        next_role = participant_roles.get(str(next_actor))
        if (
            next_actor not in {args.role, f"participant_{args.role}"}
            and not str(next_actor).endswith(f"_{args.role}")
            and next_role != args.role
        ):
            raise ApiError(f"Backend did not return control to external role {args.role!r}")
        scoped_state = participant_api.get_session(session_id)
        # The observation is passed on its own; the protocol state must not repeat it.
        protocol_state = {key: value for key, value in scoped_state.items() if key != "observation"}
        if current.get("result") in {"clarification_required", "confirmation_required"}:
            protocol_state.update(actor_safe_protocol_result(current))
        generation = agent.generate_turn(
            observation=scoped_state.get("observation", {}),
            history=participant_api.history(session_id),
            protocol_result=protocol_state,
        )
        current = participant_api.submit_message(
            session_id,
            generation.text,
            expected_revision=response_revision(scoped_state),
        )
        turns.append(
            {
                "step": step,
                "message": generation.text,
                "provider": generation.provider,
                "model": generation.model,
                "model_reported": generation.model_reported,
                "latency_ms": generation.latency_ms,
                "usage": dict(generation.usage),
                "retry_count": generation.retry_count,
            }
        )
        print(f"{args.role}> {generation.text}")
    if response_status(current) not in TERMINAL_STATUSES:
        raise ApiError(f"Agent exceeded max_messages={args.max_messages}")
    _print_json({"session_id": session_id, "status": response_status(current), "turns": turns})
    _print_json(participant_api.review(session_id))
    return 0


def command_self_play(api: NegotiationApiClient, args: argparse.Namespace) -> int:
    # Each seat samples with its own seed: base seed for the buyer, base seed + 1 for the seller.
    buyer_seed = args.seed
    seller_seed = args.seed + 1 if args.seed is not None else None
    buyer = _provider(args, "buyer_", seed=buyer_seed)
    seller = _provider(args, "seller_", seed=seller_seed)
    result = run_self_play(
        api,
        scenario_id=args.scenario,
        scenario_version=args.scenario_version,
        language=args.language,
        seats=[AgentSeat("buyer", buyer), AgentSeat("seller", seller)],
        max_messages=args.max_messages,
        run_mode=args.run_mode,
        benchmark_run_id=args.benchmark_run_id,
        trial_id=args.trial_id,
        seed=args.seed,
    )
    if args.output:
        destination = Path(args.output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(destination)
    else:
        _print_json(result)
    return 2 if result.get("status") == "technical_failure" else 0


def command_transcript_playback(api: NegotiationApiClient, args: argparse.Namespace) -> int:
    turns = load_markdown_transcript(
        args.transcript,
        player_heading=args.player_heading,
        npc_heading=args.npc_heading,
        player_role=args.player_role,
        npc_role=args.npc_role,
    )
    report = run_transcript_playback(
        api,
        source=args.transcript,
        turns=turns,
        mode=args.mode,
        scenario_id=args.scenario,
        scenario_version=args.scenario_version,
        language=args.language,
        player_role=args.player_role,
        npc_role=args.npc_role,
        finalize_for_review=args.final_review,
        admin_token=os.getenv(ADMIN_TOKEN_ENV) if args.final_review else None,
    )
    outputs: dict[str, str] = {}
    if args.output:
        destination = Path(args.output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        outputs["json_output"] = str(destination)
    if args.markdown_output:
        destination = Path(args.markdown_output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_player_markdown(report), encoding="utf-8")
        outputs["markdown_output"] = str(destination)
    if outputs:
        _print_json(
            {
                **outputs,
                "session_id": report["session_id"],
                "playback_status": report["playback_status"],
                "session_status": report["session_status"],
                "review_available": "review" in report,
                **({"divergence": report["divergence"]} if "divergence" in report else {}),
            }
        )
    else:
        _print_json(report)
    return 1 if report["playback_status"] == "diverged" else 0


def command_simple(api: NegotiationApiClient, args: argparse.Namespace) -> int:
    if args.command == "scenarios":
        _print_json(api.list_scenarios(language=args.language))
        return 0
    if args.command == "stats":
        _print_json(api.stats())
        return 0
    token = os.getenv(args.participant_token_env)
    participant_api = api.with_participant_token(token)
    if args.command == "history":
        _print_json(participant_api.history(args.session_id))
    elif args.command == "review":
        _print_json(participant_api.review(args.session_id))
    elif args.command in {"coach", "checkpoints", "compare"}:
        method = {"coach": participant_api.coaching, "checkpoints": participant_api.checkpoints,
                  "compare": participant_api.comparison}[args.command]
        _print_json(method(args.session_id))
    elif args.command == "retry":
        created = participant_api.fork(args.session_id, args.source_revision, args.idempotency_key)
        fresh = extract_participant_credentials(created)
        if not fresh:
            raise ApiError("Retry credentials were already delivered. Use the original retry process or a new idempotency key.")
        child_api = api.with_participant_token(next(iter(fresh.values())))
        return _play_existing_plain(child_api, created)
    elif args.command == "export":
        print(participant_api.export_session(args.session_id, args.output))
    else:
        raise ValueError(f"Unsupported command: {args.command}")
    return 0


def _add_global_options(parser: argparse.ArgumentParser, *, on_subcommand: bool = False) -> None:
    """Register the global options; a subcommand accepts them too, after its own name."""

    parser.add_argument(
        "--base-url",
        default=argparse.SUPPRESS if on_subcommand else None,
        help="Negotiation API base URL (default: http://127.0.0.1:8170)",
    )
    parser.add_argument(
        "--api-timeout", type=float, default=argparse.SUPPRESS if on_subcommand else 30.0
    )


def _add_session_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--scenario-version", type=int, default=1)
    parser.add_argument("--language", choices=("ru", "en"), default="ru")
    parser.add_argument("--role", choices=("buyer", "seller"), default="buyer")
    parser.add_argument("--other-role", choices=("buyer", "seller"), default="seller")
    parser.add_argument("--participant-token-env", default="NEGOTIATION_PARTICIPANT_TOKEN")


def _add_generation_options(parser: argparse.ArgumentParser, prefix: str = "") -> None:
    option = prefix.replace("_", "-")
    parser.add_argument(f"--{option}provider", choices=("openai", "qwen"), default="openai")
    parser.add_argument(f"--{option}model")
    parser.add_argument(f"--{option}api-key-env")


def _add_provider_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-messages", type=_positive_int, default=40)
    parser.add_argument("--max-output-tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--provider-timeout", type=float, default=60.0)
    parser.add_argument(
        "--provider-max-attempts",
        type=_positive_int,
        default=DEFAULT_MAX_ATTEMPTS,
        help="Attempts per provider call for rate limits, 5xx, timeouts, and connection errors",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _add_global_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scenarios = subparsers.add_parser("scenarios", help="List published scenarios")
    scenarios.add_argument("--language", choices=("ru", "en"))

    play = subparsers.add_parser("play", help="Start an interactive human session")
    _add_session_options(play)
    play.add_argument(
        "--difficulty", choices=("guided", "easy", "normal", "expert"), default="normal"
    )
    play.add_argument("--no-hints", action="store_true")
    play.add_argument("--training-file", help="JSON file with shared context and private preparation")
    play.add_argument(
        "--debug", action="store_true", help="Show Player API debug state in the lower-right pane"
    )
    play.add_argument(
        "--plain", action="store_true", help="Use the original line-oriented JSON interface"
    )

    agent = subparsers.add_parser("agent", help="Run one external agent against the built-in NPC")
    _add_session_options(agent)
    _add_generation_options(agent)
    agent.add_argument(
        "--difficulty", choices=("guided", "easy", "normal", "expert"), default="normal"
    )
    agent.add_argument("--no-hints", action="store_true")
    _add_provider_run_options(agent)

    self_play = subparsers.add_parser("self-play", help="Run two external agents")
    self_play.add_argument("--scenario", required=True)
    self_play.add_argument("--scenario-version", type=int, default=1)
    self_play.add_argument("--language", choices=("ru", "en"), default="ru")
    _add_generation_options(self_play, "buyer_")
    _add_generation_options(self_play, "seller_")
    _add_provider_run_options(self_play)
    self_play.add_argument("--run-mode", choices=("training", "benchmark"), default="benchmark")
    self_play.add_argument("--benchmark-run-id")
    self_play.add_argument("--trial-id")
    self_play.add_argument(
        "--seed",
        type=int,
        help="Base sampling seed where the selected provider supports it (buyer: seed, "
        "seller: seed + 1); reproducibility is not guaranteed",
    )
    self_play.add_argument("--output")

    playback = subparsers.add_parser(
        "transcript-playback",
        help="Play a Markdown transcript through the Player API",
    )
    playback.add_argument("transcript", help="Markdown transcript file")
    playback.add_argument("--scenario", required=True)
    playback.add_argument("--scenario-version", type=int, default=1)
    playback.add_argument("--language", choices=("ru", "en"), default="ru")
    playback.add_argument("--mode", choices=("exact", "npc-comparison"), default="exact")
    playback.add_argument("--player-heading", default="Александр")
    playback.add_argument("--npc-heading", default="Nord Systems")
    playback.add_argument("--player-role", default="buyer")
    playback.add_argument("--npc-role", default="seller")
    playback.add_argument("--output", help="Write the credential-free JSON report to this path")
    playback.add_argument(
        "--markdown-output",
        help="Write the player-visible transcript and final review to this Markdown path",
    )
    playback.add_argument(
        "--final-review",
        action="store_true",
        help=f"Close a non-terminal playback session and fetch its review; requires {ADMIN_TOKEN_ENV}",
    )

    for name in ("history", "review", "coach", "checkpoints", "compare", "retry"):
        command = subparsers.add_parser(name)
        command.add_argument("session_id")
        command.add_argument("--participant-token-env", default="NEGOTIATION_PARTICIPANT_TOKEN")
        if name == "retry":
            command.add_argument("--source-revision", required=True, type=int)
            command.add_argument("--idempotency-key")
    export = subparsers.add_parser("export", help="Export safe history and final review")
    export.add_argument("session_id")
    export.add_argument("output")
    export.add_argument("--participant-token-env", default="NEGOTIATION_PARTICIPANT_TOKEN")
    subparsers.add_parser("stats", help="Get aggregate backend statistics")
    for subparser in subparsers.choices.values():
        _add_global_options(subparser, on_subcommand=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api = NegotiationApiClient(args.base_url, timeout=args.api_timeout)
    try:
        if args.command == "play":
            if args.role == args.other_role:
                raise ValueError("--role and --other-role must differ")
            return command_play(api, args)
        if args.command == "agent":
            if args.role == args.other_role:
                raise ValueError("--role and --other-role must differ")
            return command_agent(api, args)
        if args.command == "self-play":
            return command_self_play(api, args)
        if args.command == "transcript-playback":
            return command_transcript_playback(api, args)
        return command_simple(api, args)
    except (ApiError, OSError, ProviderError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
