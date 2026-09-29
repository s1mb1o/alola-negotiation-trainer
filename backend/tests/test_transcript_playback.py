from __future__ import annotations

from urllib.parse import urlsplit

from clients.api import ApiError, NegotiationApiClient
from clients.transcript_playback import parse_markdown_transcript, run_transcript_playback


def _client_transport(test_client):
    def transport(method, url, payload, headers, timeout):
        del timeout
        parsed = urlsplit(url)
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        response = test_client.request(
            method,
            target,
            headers=dict(headers),
            **({"json": payload} if payload is not None else {}),
        )
        body = response.json()
        if response.status_code >= 400:
            raise ApiError(
                str(body.get("message") or body.get("detail") or body.get("error")),
                status=response.status_code,
                code=body.get("code"),
                error=body.get("error") if isinstance(body.get("error"), str) else None,
                details=body,
            )
        return body

    return transport


def test_exact_playback_uses_the_real_player_api(client) -> None:
    transcript = """# Reference

### Nord Systems

> Цена за 100 устройств составляет €120 000. Стандартный срок — восемь недель.

### Александр

> Качество нас устраивает, но предложение выходит за бюджет. Можно снизить стоимость?

### Nord Systems — Михаил

> Предлагаем €116 000 за основные 100 устройств.
"""
    turns = parse_markdown_transcript(
        transcript,
        player_heading="Александр",
        npc_heading="Nord Systems",
        player_role="buyer",
        npc_role="seller",
    )
    api = NegotiationApiClient("http://test", transport=_client_transport(client))
    report = run_transcript_playback(
        api,
        source="reference.md",
        turns=turns,
        mode="exact",
        scenario_id="supplier_integration_ru",
        scenario_version=1,
        language="ru",
        player_role="buyer",
        npc_role="seller",
        finalize_for_review=True,
        admin_token="test-admin",
    )

    assert report["playback_status"] == "completed", report
    assert report["submitted_turns"] == 2
    assert report["session_status"] == "aborted"
    assert report["review"]["outcome"]["termination_reason"] == "aborted"
    assert [turn["action"] for turn in report["turns"]] == [
        "opening_reference",
        "submitted",
        "submitted",
    ]
    assert report["history"]["messages"][-1]["role"] == "seller"
    assert report["history"]["messages"][-1]["content"].startswith("Предлагаем €116 000")
