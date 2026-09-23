import json
from unittest.mock import Mock, patch

from clients.api import NegotiationApiClient
from clients.cli import _create_training_session, build_parser, command_simple


def test_cli_training_file_and_commands(tmp_path):
    path = tmp_path / "training.json"
    path.write_text(json.dumps({"relationship": "successful_history", "preparation": {"target": "private"}}))
    api = Mock()
    args = build_parser().parse_args(["play", "--scenario", "saas_subscription_ru", "--training-file", str(path)])
    _create_training_session(api, args, controller="human")
    assert api.create_session.call_args.kwargs["training"]["preparation"]["target"] == "private"
    for name, method in [("coach", "coaching"), ("checkpoints", "checkpoints"), ("compare", "comparison")]:
        args = build_parser().parse_args([name, "session"])
        getattr(api.with_participant_token.return_value, method).return_value = {}
        with patch("clients.cli._print_json"):
            assert command_simple(api, args) == 0
        getattr(api.with_participant_token.return_value, method).assert_called_once_with("session")


def test_retry_keeps_new_credential_inside_interactive_client():
    api = Mock()
    child = {"session_id": "child", "participant_credentials": [{"role": "buyer", "token": "fresh-token"}]}
    api.with_participant_token.return_value.fork.return_value = child
    args = build_parser().parse_args(["retry", "parent", "--source-revision", "2", "--idempotency-key", "once"])
    with patch("clients.cli._play_existing_plain", return_value=0) as play:
        assert command_simple(api, args) == 0
        play.assert_called_once()
    api.with_participant_token.assert_any_call("fresh-token")


def test_training_api_routes_and_idempotency():
    client = NegotiationApiClient(participant_token="owner")
    with patch.object(client, "_request", return_value={}) as request:
        client.coaching("s/1")
        request.assert_called_with("POST", "/api/v1/sessions/s%2F1/coaching", {})
        client.fork("s", 2, "once")
        request.assert_called_with("POST", "/api/v1/sessions/s/fork", {"source_revision": 2, "idempotency_key": "once"})
