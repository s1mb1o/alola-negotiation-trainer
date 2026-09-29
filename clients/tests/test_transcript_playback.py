from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from clients.cli import build_parser, command_transcript_playback
from clients.transcript_playback import (
    load_markdown_transcript,
    parse_markdown_transcript,
    render_player_markdown,
    run_transcript_playback,
)


TRANSCRIPT = """# Negotiation

## Start

### Nord Systems

> Opening paragraph.
>
> Opening question?

## Turn 1

### Alexander

> We need a lower price.

### Nord Systems — Michael

> We can discuss the price.
> - Option one
> - Option two
"""


class PlaybackApi:
    def __init__(self, owner: str | None = None, shared: dict | None = None) -> None:
        self.owner = owner
        self.shared = shared or {
            "revision": 0,
            "next_actor": "participant_buyer",
            "status": "active",
            "messages": [],
            "events": [],
            "participants": None,
            "same_actor": False,
            "submits": [],
        }

    def create_session(self, **kwargs):
        self.shared["participants"] = kwargs["participants"]
        comparison = any(item["controller"] == "built_in_npc" for item in kwargs["participants"])
        if comparison:
            self.shared["messages"].append(
                {
                    "session_revision": 0,
                    "participant_id": "participant_seller",
                    "role": "seller",
                    "content": "Current greeting.",
                }
            )
        credentials = {"buyer": "buyer-secret"}
        if not comparison:
            credentials["seller"] = "seller-secret"
        return {
            "session_id": "sess_playback",
            "revision": 0,
            "status": "active",
            "next_actor": "participant_buyer",
            "participants": [
                {"participant_id": "participant_buyer", "role": "buyer"},
                {"participant_id": "participant_seller", "role": "seller"},
            ],
            "participant_credentials": credentials,
            "observation": {
                "current_public_terms": {"price": 120_000},
                "active_offers": [],
            },
        }

    def with_participant_token(self, token):
        owner = {"buyer-secret": "buyer", "seller-secret": "seller"}[token]
        return PlaybackApi(owner, self.shared)

    def history(self, session_id):
        return {
            "session_id": session_id,
            "revision": self.shared["revision"],
            "messages": list(self.shared["messages"]),
            "events": list(self.shared["events"]),
        }

    def submit_message(self, session_id, message, *, expected_revision, idempotency_key=None):
        assert expected_revision == self.shared["revision"]
        assert self.owner in {"buyer", "seller"}
        self.shared["revision"] += 1
        revision = self.shared["revision"]
        self.shared["submits"].append((self.owner, message))
        self.shared["messages"].append(
            {
                "session_revision": revision,
                "participant_id": f"participant_{self.owner}",
                "role": self.owner,
                "content": message,
            }
        )
        comparison = any(
            item["controller"] == "built_in_npc" for item in self.shared["participants"]
        )
        if comparison:
            self.shared["messages"].append(
                {
                    "session_revision": revision,
                    "participant_id": "participant_seller",
                    "role": "seller",
                    "content": "Current reply.",
                }
            )
            next_actor = "participant_buyer"
        elif self.shared["same_actor"]:
            next_actor = f"participant_{self.owner}"
        else:
            next_actor = "participant_seller" if self.owner == "buyer" else "participant_buyer"
        self.shared["next_actor"] = next_actor
        self.shared["events"].append(
            {
                "event_id": f"event_{revision}",
                "session_revision": revision,
                "participant_id": f"participant_{self.owner}",
                "type": "participant.message",
                "payload": {},
            }
        )
        return {
            "result": "clarification_required" if self.shared["same_actor"] else "turn_committed",
            "revision": revision,
            "status": self.shared["status"],
            "next_actor": next_actor,
            "observation": {
                "current_public_terms": {"price": 116_000},
                "active_offers": [],
            },
        }

    def close_session(
        self, session_id, *, expected_revision, reason, admin_token, idempotency_key=None
    ):
        assert expected_revision == self.shared["revision"]
        assert admin_token == "test-admin"
        self.shared["revision"] += 1
        self.shared["status"] = "aborted"
        self.shared["next_actor"] = None
        self.shared["events"].append(
            {
                "event_id": "event_closed",
                "session_revision": self.shared["revision"],
                "participant_id": None,
                "type": "session.aborted",
                "payload": {"reason": reason},
            }
        )
        return {
            "session_id": session_id,
            "revision": self.shared["revision"],
            "status": "aborted",
            "next_actor": None,
            "terminal_reason": reason,
        }

    def review(self, session_id):
        assert self.shared["status"] == "aborted"
        return {
            "session_id": session_id,
            "outcome": {
                "agreement": False,
                "termination_reason": "aborted",
                "participant_utility": 36,
            },
            "scores": {"outcome_score": 36, "skill_score": 62.5},
            "skills": {
                "probing": 35,
                "package_design": 75,
                "clarity": 90,
                "conditional_trading": 50,
            },
            "key_moments": [
                {
                    "title": "Встречное предложение",
                    "summary": "Игрок предложил новый пакет.",
                }
            ],
            "recommendations": [
                {"skill": "probing", "text": "Задавайте больше диагностических вопросов."}
            ],
        }


class TranscriptParserTest(unittest.TestCase):
    def test_extracts_configured_speakers_and_preserves_paragraphs(self):
        turns = parse_markdown_transcript(
            TRANSCRIPT,
            player_heading="Alexander",
            npc_heading="Nord Systems",
            player_role="buyer",
            npc_role="seller",
        )
        self.assertEqual([turn.role for turn in turns], ["seller", "buyer", "seller"])
        self.assertEqual(turns[0].message, "Opening paragraph.\n\nOpening question?")
        self.assertEqual(
            turns[2].message,
            "We can discuss the price.\n- Option one\n- Option two",
        )
        self.assertEqual(turns[2].heading, "Nord Systems — Michael")

    def test_loads_utf8_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.md"
            path.write_text(TRANSCRIPT, encoding="utf-8")
            turns = load_markdown_transcript(
                path,
                player_heading="Alexander",
                npc_heading="Nord Systems",
                player_role="buyer",
                npc_role="seller",
            )
        self.assertEqual(len(turns), 3)

    def test_requires_distinct_speaker_labels(self):
        with self.assertRaisesRegex(ValueError, "headings must differ"):
            parse_markdown_transcript(
                TRANSCRIPT,
                player_heading="same",
                npc_heading="same",
                player_role="buyer",
                npc_role="seller",
            )


class TranscriptPlaybackTest(unittest.TestCase):
    def _turns(self):
        return parse_markdown_transcript(
            TRANSCRIPT,
            player_heading="Alexander",
            npc_heading="Nord Systems",
            player_role="buyer",
            npc_role="seller",
        )

    def test_exact_mode_submits_both_roles_after_the_opening_reference(self):
        api = PlaybackApi()
        report = run_transcript_playback(
            api,
            source="transcript.md",
            turns=self._turns(),
            mode="exact",
            scenario_id="supplier_integration_en",
            scenario_version=1,
            language="en",
            player_role="buyer",
            npc_role="seller",
        )
        self.assertEqual(report["playback_status"], "completed")
        self.assertEqual(report["submitted_turns"], 2)
        self.assertEqual(
            [turn["action"] for turn in report["turns"]],
            ["opening_reference", "submitted", "submitted"],
        )
        self.assertEqual(
            api.shared["participants"],
            [
                {"role": "buyer", "controller": "scripted_bot"},
                {"role": "seller", "controller": "scripted_bot"},
            ],
        )
        self.assertEqual([role for role, _ in api.shared["submits"]], ["buyer", "seller"])
        serialized = json.dumps(report)
        self.assertNotIn("buyer-secret", serialized)
        self.assertNotIn("seller-secret", serialized)
        self.assertIn("new_events", report["turns"][1]["engine"])

    def test_exact_mode_records_a_turn_divergence(self):
        api = PlaybackApi()
        api.shared["same_actor"] = True
        report = run_transcript_playback(
            api,
            source="transcript.md",
            turns=self._turns(),
            mode="exact",
            scenario_id="supplier_integration_en",
            scenario_version=1,
            language="en",
            player_role="buyer",
            npc_role="seller",
        )
        self.assertEqual(report["playback_status"], "diverged")
        self.assertEqual(report["divergence"]["kind"], "turn_mismatch")
        self.assertEqual(report["divergence"]["expected_role"], "buyer")
        self.assertEqual(report["divergence"]["recorded_role"], "seller")

    def test_npc_comparison_submits_only_player_messages(self):
        api = PlaybackApi()
        report = run_transcript_playback(
            api,
            source="transcript.md",
            turns=self._turns(),
            mode="npc-comparison",
            scenario_id="supplier_integration_en",
            scenario_version=1,
            language="en",
            player_role="buyer",
            npc_role="seller",
        )
        self.assertEqual(report["playback_status"], "completed")
        self.assertEqual(report["submitted_turns"], 1)
        self.assertEqual([role for role, _ in api.shared["submits"]], ["buyer"])
        references = [turn for turn in report["turns"] if turn["action"] == "reference_only"]
        self.assertEqual(len(references), 2)
        self.assertEqual(
            references[0]["comparison"]["engine_messages"][0]["content"],
            "Current greeting.",
        )
        self.assertEqual(
            references[1]["comparison"]["engine_messages"][0]["content"],
            "Current reply.",
        )

    def test_final_review_closes_the_session_and_renders_player_markdown(self):
        api = PlaybackApi()
        report = run_transcript_playback(
            api,
            source="transcript.md",
            turns=self._turns(),
            mode="npc-comparison",
            scenario_id="supplier_integration_en",
            scenario_version=1,
            language="en",
            player_role="buyer",
            npc_role="seller",
            finalize_for_review=True,
            admin_token="test-admin",
        )
        markdown = render_player_markdown(report)

        self.assertEqual(report["session_status"], "aborted")
        self.assertEqual(
            report["finalization"]["terminal_reason"], "Transcript playback source exhausted."
        )
        self.assertEqual(report["review"]["scores"]["skill_score"], 62.5)
        self.assertIn("## Диалог", markdown)
        self.assertIn("## Итоговый разбор", markdown)
        self.assertIn("### Рекомендации", markdown)
        self.assertLess(markdown.index("## Диалог"), markdown.index("## Итоговый разбор"))
        self.assertNotIn("buyer-secret", markdown)

    def test_cli_exposes_both_modes(self):
        args = build_parser().parse_args(
            [
                "transcript-playback",
                "chat.md",
                "--scenario",
                "supplier_integration_ru",
                "--mode",
                "npc-comparison",
            ]
        )
        self.assertEqual(args.mode, "npc-comparison")
        self.assertEqual(args.player_heading, "Александр")
        self.assertEqual(args.npc_heading, "Nord Systems")

    def test_cli_writes_a_credential_free_report(self):
        api = PlaybackApi()
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "chat.md"
            output = Path(directory) / "report.json"
            source.write_text(TRANSCRIPT, encoding="utf-8")
            args = build_parser().parse_args(
                [
                    "transcript-playback",
                    str(source),
                    "--scenario",
                    "supplier_integration_en",
                    "--language",
                    "en",
                    "--player-heading",
                    "Alexander",
                    "--output",
                    str(output),
                ]
            )
            with redirect_stdout(stdout):
                code = command_transcript_playback(api, args)
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(report["playback_status"], "completed")
        self.assertNotIn("buyer-secret", json.dumps(report))
        self.assertIn("sess_playback", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
