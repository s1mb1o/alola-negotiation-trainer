"""Opt-in human training, private reviews, and exact checkpoint branching."""

from __future__ import annotations

import json
import secrets
import uuid

from .coaching import generate_coaching
from .dialogue import redact_untrusted_credentials
from .models import TERMINAL_STATUSES
from .player_assistance import generate_player_reply
from .scenarios import canonical_json, digest
from .training import classify_social, evaluate_targets, npc_training_context


def result(status, payload):
    from .service import ServiceResult
    return ServiceResult(status, payload)


def error(code, status=409):
    return result(status, {"error": code, "message": code.replace("_", " ")})


class TrainingServiceMixin:
    MAX_TRAINING_REWINDS = 3

    def _training_preclassify(self, session_id, token, request, request_digest):
        if self.social_provider is None:
            return []
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            state = json.loads(session["state_json"])
            training = state.get("training")
            if (not training or training["owner_id"] != participant["id"]
                    or session["status"] != "active" or request.expected_revision != session["revision"]
                    or session["next_participant_id"] != participant["id"]
                    or self._pending_render_result(connection, session_id, session["revision"]) is not None
                    or self._idempotency_result(connection, f"message:{session_id}:{participant['id']}",
                                                request.idempotency_key, request_digest) is not None):
                return []
            def sanitize(text):
                return redact_untrusted_credentials(text, token, *self._known_redaction_secrets)
            message = sanitize(request.message)
            conversation = [dict(row) for row in connection.execute(
                "SELECT role, content FROM (SELECT id, role, content FROM messages WHERE session_id = ? "
                "ORDER BY id DESC LIMIT 6) ORDER BY id", (session_id,))]
            for turn in conversation:
                turn["content"] = sanitize(turn["content"])
            context = npc_training_context(training, session["language"], message)
        return classify_social(self.social_provider, message, conversation, context)

    def _capture_training_checkpoint(self, connection, session, state):
        training = state.get("training")
        if (not training or session["status"] != "active"
                or session["next_participant_id"] != training["owner_id"]):
            return
        snapshot = {"session": dict(session), "offers": [dict(row) for row in connection.execute(
            "SELECT * FROM offers WHERE session_id = ?", (session["id"],))]}
        for table in ("messages", "events"):
            snapshot[f"last_{table}_id"] = connection.execute(
                f"SELECT COALESCE(MAX(id), 0) FROM {table} WHERE session_id = ?", (session["id"],)
            ).fetchone()[0]
        connection.execute("INSERT OR IGNORE INTO training_checkpoints VALUES (?, ?, ?)",
                           (session["id"], session["revision"], canonical_json(snapshot)))

    def _training_checkpoints(self, connection, session_id):
        return [{"source_revision": row["revision"]} for row in connection.execute(
            "SELECT revision FROM training_checkpoints WHERE session_id = ? ORDER BY revision", (session_id,))]

    @staticmethod
    def _training_rewind_root(state, session_id):
        return state.get("rewind_root_session_id") or session_id

    def _training_rewind_status(self, connection, session, state):
        root_session_id = self._training_rewind_root(state, session["id"])
        used = int(connection.execute(
            "SELECT COUNT(*) FROM training_rewinds WHERE root_session_id = ?",
            (root_session_id,),
        ).fetchone()[0])
        revisions = [int(row["revision"]) for row in connection.execute(
            "SELECT checkpoint.revision FROM training_checkpoints AS checkpoint "
            "WHERE checkpoint.session_id = ? AND checkpoint.revision < ? AND EXISTS ("
            "SELECT 1 FROM messages AS message JOIN participants AS participant "
            "ON participant.id = message.participant_id "
            "WHERE message.session_id = checkpoint.session_id "
            "AND message.session_revision = checkpoint.revision "
            "AND participant.controller = 'built_in_npc') "
            "ORDER BY checkpoint.revision",
            (session["id"], int(session["revision"])),
        )]
        remaining = max(0, self.MAX_TRAINING_REWINDS - used)
        return {
            "limit": self.MAX_TRAINING_REWINDS,
            "used": used,
            "remaining": remaining,
            "available": session["status"] == "active" and remaining > 0 and bool(revisions),
            "eligible_source_revisions": revisions,
        }

    def get_training_checkpoints(self, session_id, token):
        with self.database.read_connection() as connection:
            session, participant = self._authenticated_rows(connection, session_id, token)
            training = json.loads(session["state_json"]).get("training", {})
            if session["run_mode"] != "training" or training.get("owner_id") != participant["id"]:
                return error("training_not_available")
            return result(200, {"session_id": session_id, "checkpoints": self._training_checkpoints(connection, session_id)})

    def _training_review_projection(self, connection, session, participant, public):
        state = json.loads(session["state_json"])
        training = state.get("training", {})
        if training.get("owner_id") != participant["id"]:
            return {}
        scenario = self._scenario_source(connection, session)
        evidence = [{"ref": f"message:{row['id']}", "source_revision": row["session_revision"],
                     "role": row["role"], "is_player": row["participant_id"] == participant["id"],
                     "text": row["content"]} for row in connection.execute(
            "SELECT id, session_revision, participant_id, role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session["id"],))]
        changes = [{"source_revision": row["session_revision"], **json.loads(row["private_payload_json"])}
                   for row in connection.execute("SELECT session_revision, private_payload_json FROM events "
                   "WHERE session_id = ? AND type = 'training.social.updated' ORDER BY id", (session["id"],))]
        offers = [{"source_revision": row["session_revision"], "event_id": row["event_id"],
                   "type": row["type"], "terms": json.loads(row["public_payload_json"]).get("terms", {})}
                  for row in connection.execute("SELECT * FROM events WHERE session_id = ? AND type IN "
                  "('proposal.created', 'proposal.revised', 'offer.created', 'offer.countered', 'agreement.reached') ORDER BY id",
                  (session["id"],))]
        coaching = connection.execute("SELECT status, result_json FROM training_reviews WHERE session_id = ?",
                                      (session["id"],)).fetchone()
        return {"training": {
            "version": training["version"], "preparation": training["setup"]["preparation"],
            "role_brief": self._role_brief(scenario, participant["role"], session["language"]),
            "economic_baseline": {
                "batna_utility": scenario["roles"][participant["role"]]["batna"]["utility"],
                "reservation_utility": scenario["utility_model"]["role_models"][participant["role"]]["reservation_utility"],
            },
            "initial_context": {
                key: training["setup"].get(key, "")
                for key in ("profile", "relationship", "player_name", "shared_background")
            },
            "goal_comparison": evaluate_targets(training, public["outcome"]["agreement_terms"]
                if public["outcome"]["agreement"] else None, scenario["terms"]["definitions"]),
            "initial_social": training["initial_social"], "final_social": training["social"],
            "social_rule_version": training["social_rule_version"], "social_events": changes,
            "evidence": evidence, "offer_history": offers,
            "checkpoints": self._training_checkpoints(connection, session["id"]),
            "parent_session_id": state.get("parent_session_id"), "source_revision": state.get("source_revision"),
            "informed_practice": bool(state.get("parent_session_id")),
            "skill_scores_validated": False,
            "coaching": ({"status": coaching["status"], **json.loads(coaching["result_json"])}
                         if coaching else {"status": "not_requested"}),
        }}

    def request_coaching(self, session_id, token):
        # The report gate executes before any claim or model call, including benchmark sealing.
        with self.locks.for_session(session_id):
            reviewed = self.get_review(session_id, token)
            if reviewed.status_code != 200:
                return reviewed
            report = reviewed.payload
            if "training" not in report:
                return error("training_not_available")
            with self.database.write_transaction() as connection:
                session, participant = self._authenticated_rows(connection, session_id, token)
                connection.execute("UPDATE training_reviews SET status = 'unavailable', result_json = ?, "
                    "completed_at = CURRENT_TIMESTAMP WHERE session_id = ? AND status = 'pending' "
                    "AND started_at < datetime('now', '-3 minutes')",
                    (canonical_json({"reason": "analysis_interrupted"}), session_id))
                existing = connection.execute("SELECT * FROM training_reviews WHERE session_id = ?", (session_id,)).fetchone()
                if existing:
                    return result(202 if existing["status"] == "pending" else 200,
                                  {"status": existing["status"], **json.loads(existing["result_json"])})
                connection.execute("INSERT INTO training_reviews(session_id, participant_id, source_revision, status) "
                                   "VALUES (?, ?, ?, 'pending')", (session_id, participant["id"], session["revision"]))
                language = session["language"]
            data = report["training"]
            package = {"language": language, "revision": report["revision"], "outcome": report["outcome"],
                       "preparation": data["preparation"], "goal_comparison": data["goal_comparison"],
                       "role_brief": data["role_brief"], "economic_baseline": data["economic_baseline"],
                       "initial_context": data["initial_context"],
                       "evidence": data["evidence"], "offer_history": data["offer_history"]}
            # Bound provider context. Exact evidence references remain valid when truncated.
            selected, budget = [], 28000
            for item in reversed(package["evidence"][-80:]):
                excerpt = {**item, "text": item["text"][:1600]}
                if len(item["text"]) > 1600:
                    excerpt["excerpt_truncated"] = True
                size = len(json.dumps(excerpt, ensure_ascii=False))
                if size > budget:
                    break
                budget -= size
                selected.append(excerpt)
            package["evidence_truncated"] = len(selected) < len(package["evidence"]) or any(
                len(item["text"]) > 1600 for item in package["evidence"])
            package["evidence"] = list(reversed(selected))
            package["offer_history"] = package["offer_history"][-12:]
            def sanitize(text):
                return redact_untrusted_credentials(text, token, *self._known_redaction_secrets)
            package = json.loads(sanitize(json.dumps(package, ensure_ascii=False)))
            analysis = generate_coaching(self.review_provider, package, sanitize)
            analysis["evidence_truncated"] = package["evidence_truncated"]
            with self.database.write_transaction() as connection:
                connection.execute("UPDATE training_reviews SET status = ?, result_json = ?, completed_at = CURRENT_TIMESTAMP "
                                   "WHERE session_id = ? AND status = 'pending' AND source_revision = ?",
                                   (analysis["status"], canonical_json(analysis), session_id, report["revision"]))
            return result(200, analysis)

    def request_player_assist(self, session_id, token, request):
        lock = self.locks.for_session(session_id)
        request_digest = digest(request.model_dump(mode="json"))
        with lock:
            with self.database.write_transaction() as connection:
                session, participant = self._authenticated_rows(connection, session_id, token)
                scope = f"player_assist:{session_id}:{participant['id']}"
                repeated = self._idempotency_result(
                    connection, scope, request.idempotency_key, request_digest
                )
                if repeated is not None:
                    return repeated
                state = json.loads(session["state_json"])
                training = state.get("training", {})
                if (
                    session["run_mode"] != "training"
                    or training.get("owner_id") != participant["id"]
                ):
                    return error("player_assist_not_available")
                if session["status"] != "active":
                    return error("session_terminal")
                if int(session["revision"]) != request.expected_revision:
                    return result(409, {
                        "error": "revision_conflict",
                        "message": "The session revision changed",
                        "revision": int(session["revision"]),
                    })
                if session["next_participant_id"] != participant["id"]:
                    return error("not_your_turn")
                scenario = self._scenario_source(connection, session)
                observation = self._observation(
                    connection, session, participant, scenario, state
                )
                pending = state.get("pending_confirmation") or {}
                pending_confirmation = (
                    {
                        "offer_id": pending["offer_id"],
                        "offer_revision": pending["offer_revision"],
                        "terms": pending["terms"],
                    }
                    if pending.get("participant_id") == participant["id"]
                    else None
                )
                pending_clarification = state.get("pending_clarification") or {}
                pending_clarification = (
                    {
                        key: value
                        for key, value in pending_clarification.items()
                        if key != "participant_id"
                    }
                    if pending_clarification.get("participant_id") == participant["id"]
                    else None
                )
                package = {
                    "language": session["language"],
                    "revision": int(session["revision"]),
                    "role": participant["role"],
                    "role_brief": observation["role_brief"],
                    "private_preparation": training["setup"]["preparation"],
                    "relationship": training["setup"]["relationship"],
                    "shared_background": training["setup"]["shared_background"],
                    "conversation": observation["conversation"][-16:],
                    "active_offers": observation["active_offers"],
                    "preliminary_proposals": observation.get("preliminary_proposals"),
                    "current_public_terms": observation.get("current_public_terms"),
                    "pending_confirmation": pending_confirmation,
                    "pending_clarification": pending_clarification,
                }

            def sanitize(text):
                return redact_untrusted_credentials(
                    text, token, *self._known_redaction_secrets
                )

            package = json.loads(sanitize(json.dumps(package, ensure_ascii=False)))
            generated = generate_player_reply(
                self.player_assist_provider,
                package,
                sanitize,
            )

            with self.database.write_transaction() as connection:
                current, current_participant = self._authenticated_rows(
                    connection, session_id, token
                )
                repeated = self._idempotency_result(
                    connection, scope, request.idempotency_key, request_digest
                )
                if repeated is not None:
                    return repeated
                if (
                    int(current["revision"]) != request.expected_revision
                    or current["next_participant_id"] != current_participant["id"]
                    or current["status"] != "active"
                ):
                    response = result(409, {
                        "error": "revision_conflict",
                        "message": "The session changed while the reply was generated",
                        "revision": int(current["revision"]),
                    })
                elif generated["status"] != "complete":
                    response = result(503, {
                        "error": "player_assist_unavailable",
                        "message": "Player-side reply generation is unavailable",
                    })
                else:
                    response = result(200, {
                        "session_id": session_id,
                        "revision": int(current["revision"]),
                        "message": generated["message"],
                        "prompt_version": generated["prompt_version"],
                        "provider": generated["provider"],
                        "model": generated["model"],
                    })
                self._save_idempotency(
                    connection,
                    scope,
                    request.idempotency_key,
                    request_digest,
                    response,
                )
                return response

    def _copy_training_branch(
        self,
        connection,
        parent,
        owner,
        state,
        request,
        *,
        event_type,
        rewind_root_id=None,
    ):
        from .service import _token_hash
        from .supply_protocol import supply_envelope

        checkpoint = connection.execute(
            "SELECT snapshot_json FROM training_checkpoints "
            "WHERE session_id = ? AND revision = ?",
            (parent["id"], request.source_revision),
        ).fetchone()
        if checkpoint is None:
            return error("checkpoint_not_available", 404)
        snapshot = json.loads(checkpoint["snapshot_json"])
        child_id = "sess_" + uuid.uuid4().hex[:24]
        participants = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM participants WHERE session_id = ? ORDER BY created_at, id",
                (parent["id"],),
            )
        ]
        mapping = {
            parent["id"]: child_id,
            **{
                actor["id"]: f"participant_{child_id[5:]}_{actor['role']}"
                for actor in participants
            },
        }
        events = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM events WHERE session_id = ? AND id <= ? ORDER BY id",
                (parent["id"], snapshot["last_events_id"]),
            )
        ]
        mapping.update({row["event_id"]: "evt_" + uuid.uuid4().hex for row in events})

        def remap(value):
            if isinstance(value, str):
                return mapping.get(value, value)
            if isinstance(value, list):
                return [remap(item) for item in value]
            if isinstance(value, dict):
                return {mapping.get(key, key): remap(item) for key, item in value.items()}
            return value

        def insert(table, row, omit=()):
            row = {key: value for key, value in row.items() if key not in omit}
            columns = ", ".join(row)
            cursor = connection.execute(
                f"INSERT INTO {table}({columns}) VALUES ({','.join('?' for _ in row)})",
                tuple(row.values()),
            )
            return cursor.lastrowid

        root_session_id = rewind_root_id or self._training_rewind_root(state, parent["id"])
        child = remap(snapshot["session"])
        child_state = remap(json.loads(child["state_json"]))
        child_state.update(
            parent_session_id=parent["id"],
            source_revision=request.source_revision,
            rewind_root_session_id=root_session_id,
        )
        child["state_json"] = canonical_json(child_state)
        insert("sessions", child, ("created_at", "updated_at"))
        credentials = []
        for actor in participants:
            copied = remap(actor)
            if actor["controller"] == "human":
                fresh_token = "nt_" + secrets.token_urlsafe(32)
                copied["token_hash"] = _token_hash(fresh_token)
                credentials.append(
                    {
                        "participant_id": copied["id"],
                        "role": copied["role"],
                        "token": fresh_token,
                    }
                )
            else:
                copied["token_hash"] = None
            insert("participants", copied, ("created_at",))
        for offer in snapshot["offers"]:
            insert("offers", remap(offer))

        message_id_mapping = {0: 0}
        for row in connection.execute(
            "SELECT * FROM messages WHERE session_id = ? AND id <= ? ORDER BY id",
            (parent["id"], snapshot["last_messages_id"]),
        ).fetchall():
            message_id_mapping[int(row["id"])] = int(
                insert("messages", remap(dict(row)), ("id",))
            )
        event_id_mapping = {0: 0}
        for row in events:
            copied = remap(row)
            for name in ("public_payload_json", "private_payload_json"):
                copied[name] = canonical_json(remap(json.loads(copied[name])))
            event_id_mapping[int(row["id"])] = int(insert("events", copied, ("id",)))

        for row in connection.execute(
            "SELECT revision, snapshot_json FROM training_checkpoints "
            "WHERE session_id = ? AND revision < ? ORDER BY revision",
            (parent["id"], request.source_revision),
        ):
            earlier = json.loads(row["snapshot_json"])
            earlier_session = remap(earlier["session"])
            earlier_state = remap(json.loads(earlier_session["state_json"]))
            earlier_state["rewind_root_session_id"] = root_session_id
            earlier_session["state_json"] = canonical_json(earlier_state)
            earlier_snapshot = {
                "session": earlier_session,
                "offers": remap(earlier["offers"]),
                "last_messages_id": message_id_mapping[int(earlier["last_messages_id"])],
                "last_events_id": event_id_mapping[int(earlier["last_events_id"])],
            }
            connection.execute(
                "INSERT INTO training_checkpoints(session_id, revision, snapshot_json) "
                "VALUES (?, ?, ?)",
                (child_id, int(row["revision"]), canonical_json(earlier_snapshot)),
            )

        self._insert_event(
            connection,
            child_id,
            child["revision"],
            mapping[owner["id"]],
            event_type,
            {
                "parent_session_id": parent["id"],
                "source_revision": request.source_revision,
                "informed_practice": True,
            },
            {},
        )
        if event_type == "training.rewound":
            connection.execute(
                "INSERT INTO training_rewinds("
                "root_session_id, source_session_id, child_session_id, source_revision, owner_role"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    root_session_id,
                    parent["id"],
                    child_id,
                    request.source_revision,
                    owner["role"],
                ),
            )

        child_row = self._session_row(connection, child_id)
        self._capture_training_checkpoint(connection, child_row, child_state)
        scenario = self._scenario_source(connection, child_row)
        child_owner = self._participant_row(connection, mapping[owner["id"]])
        pending = child_state.get("pending_confirmation")
        payload = {
            "session_id": child_id,
            "revision": child["revision"],
            "status": child["status"],
            "next_actor": child["next_participant_id"],
            "scenario_id": child["scenario_id"],
            "scenario_version": child["scenario_version"],
            "language": child["language"],
            "parent_session_id": parent["id"],
            "source_revision": request.source_revision,
            "round": child["round"],
            "substantive_turn_count": child["substantive_turn_count"],
            "difficulty": child["difficulty"],
            "hints_enabled": bool(child["hints_enabled"]),
            "pending_confirmation": (
                {key: value for key, value in pending.items() if key != "participant_id"}
                if pending and pending.get("participant_id") == child_owner["id"]
                else None
            ),
            **supply_envelope(scenario, child_state, child_owner["id"]),
            "participant_credentials": credentials,
            "participant_token": credentials[0]["token"],
            "observation": self._observation(
                connection, child_row, child_owner, scenario, child_state
            ),
        }
        return result(201, payload)

    def fork_training_session(self, session_id, token, request):
        with self.locks.for_session(session_id), self.database.write_transaction() as connection:
            parent, owner = self._authenticated_rows(connection, session_id, token)
            state = json.loads(parent["state_json"])
            if (
                parent["run_mode"] != "training"
                or state.get("training", {}).get("owner_id") != owner["id"]
                or parent["status"] not in TERMINAL_STATUSES
            ):
                return error("retry_requires_completed_human_training")
            scope = f"fork:{session_id}:{owner['id']}"
            request_digest = digest(request.model_dump(mode="json"))
            repeated = self._idempotency_result(
                connection, scope, request.idempotency_key, request_digest
            )
            if repeated is not None:
                return repeated
            response = self._copy_training_branch(
                connection,
                parent,
                owner,
                state,
                request,
                event_type="training.forked",
            )
            if response.status_code == 201:
                self._save_idempotency(
                    connection,
                    scope,
                    request.idempotency_key,
                    request_digest,
                    response,
                    contains_credentials=True,
                )
            return response

    def rewind_training_session(self, session_id, token, request):
        with self.locks.for_session(session_id), self.database.write_transaction() as connection:
            parent, owner = self._authenticated_rows(connection, session_id, token)
            state = json.loads(parent["state_json"])
            if (
                parent["run_mode"] != "training"
                or state.get("training", {}).get("owner_id") != owner["id"]
                or parent["status"] != "active"
            ):
                return error("rewind_not_available")
            scope = f"rewind:{session_id}:{owner['id']}"
            request_digest = digest(request.model_dump(mode="json"))
            repeated = self._idempotency_result(
                connection, scope, request.idempotency_key, request_digest
            )
            if repeated is not None:
                return repeated
            eligible = self._training_rewind_status(connection, parent, state)
            if request.source_revision not in eligible["eligible_source_revisions"]:
                return error("rewind_checkpoint_not_available", 404)
            if eligible["remaining"] <= 0:
                return error("rewind_limit_exhausted")
            root_session_id = self._training_rewind_root(state, session_id)
            response = self._copy_training_branch(
                connection,
                parent,
                owner,
                state,
                request,
                event_type="training.rewound",
                rewind_root_id=root_session_id,
            )
            if response.status_code == 201:
                self._save_idempotency(
                    connection,
                    scope,
                    request.idempotency_key,
                    request_digest,
                    response,
                    contains_credentials=True,
                )
            return response

    def compare_training(self, session_id, token):
        reviewed = self.get_review(session_id, token)
        if reviewed.status_code != 200:
            return reviewed
        with self.database.read_connection() as connection:
            child, actor = self._authenticated_rows(connection, session_id, token)
            state = json.loads(child["state_json"])
            parent_id = state.get("parent_session_id")
            if (not parent_id or child["run_mode"] != "training"
                    or state.get("training", {}).get("owner_id") != actor["id"]):
                return error("comparison_not_available")
            parent = self._session_row(connection, parent_id)
            row = connection.execute("SELECT public_json, private_json FROM reviews WHERE session_id = ?", (parent_id,)).fetchone()
            if row is None or parent["status"] not in TERMINAL_STATUSES:
                return error("parent_review_not_ready")
            public = json.loads(row["public_json"])
            own = json.loads(row["private_json"])["participant_scores"][actor["role"]]
            prior = {**public["outcome"], "participant_utility": own["utility"], "reservation_comparison": own["reservation_comparison"]}
            current = reviewed.payload["outcome"]
            return result(200, {"parent_session_id": parent_id, "session_id": session_id,
                "source_revision": state["source_revision"], "informed_practice": True,
                "same_scenario_version": parent["compiled_scenario_digest"] == child["compiled_scenario_digest"],
                "same_initial_conditions_at_checkpoint": True, "role": actor["role"],
                "before": prior, "after": current,
                "utility_delta": round(current["participant_utility"] - prior["participant_utility"], 6),
                "causal_improvement_claim": False})
