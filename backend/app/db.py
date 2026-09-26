from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .scenarios import CompiledScenario, canonical_json


MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE scenario_versions (
        scenario_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        title TEXT NOT NULL,
        language TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        compiler_version TEXT NOT NULL,
        compiled_digest TEXT NOT NULL,
        source_json TEXT NOT NULL,
        public_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (scenario_id, version)
    );

    CREATE TABLE sessions (
        id TEXT PRIMARY KEY,
        scenario_id TEXT NOT NULL,
        scenario_version INTEGER NOT NULL,
        scenario_content_digest TEXT NOT NULL,
        scenario_compiler_version TEXT NOT NULL,
        compiled_scenario_digest TEXT NOT NULL,
        status TEXT NOT NULL,
        revision INTEGER NOT NULL,
        round INTEGER NOT NULL,
        substantive_turn_count INTEGER NOT NULL,
        next_participant_id TEXT,
        difficulty TEXT NOT NULL,
        language TEXT NOT NULL,
        run_mode TEXT NOT NULL,
        hints_enabled INTEGER NOT NULL,
        run_metadata_json TEXT NOT NULL,
        state_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (scenario_id, scenario_version)
            REFERENCES scenario_versions(scenario_id, version)
    );

    CREATE TABLE participants (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        controller TEXT NOT NULL,
        token_hash TEXT,
        provenance_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (session_id, role),
        UNIQUE (token_hash),
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );

    CREATE TABLE offers (
        session_id TEXT NOT NULL,
        offer_id TEXT NOT NULL,
        offer_revision INTEGER NOT NULL,
        proposer_participant_id TEXT NOT NULL,
        terms_json TEXT NOT NULL,
        status TEXT NOT NULL,
        created_session_revision INTEGER NOT NULL,
        PRIMARY KEY (session_id, offer_id, offer_revision),
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );

    CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        session_revision INTEGER NOT NULL,
        participant_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        language TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );

    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        session_id TEXT NOT NULL,
        session_revision INTEGER NOT NULL,
        participant_id TEXT,
        type TEXT NOT NULL,
        public_payload_json TEXT NOT NULL,
        private_payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );

    CREATE TABLE reviews (
        session_id TEXT PRIMARY KEY,
        terminal_revision INTEGER NOT NULL,
        public_json TEXT NOT NULL,
        private_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );

    CREATE TABLE idempotency_results (
        scope TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        response_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (scope, idempotency_key)
    );

    CREATE INDEX idx_participants_session ON participants(session_id);
    CREATE INDEX idx_messages_session_revision ON messages(session_id, session_revision, id);
    CREATE INDEX idx_events_session_revision ON events(session_id, session_revision, id);
    CREATE INDEX idx_sessions_status ON sessions(status);
    """,
    """
    UPDATE participants
    SET token_hash = NULL
    WHERE session_id IN (
        SELECT json_extract(response_json, '$.session_id')
        FROM idempotency_results
        WHERE scope = 'create_session'
          AND (
              instr(response_json, 'participant_credentials') > 0
              OR instr(response_json, 'participant_token') > 0
          )
    );

    DELETE FROM idempotency_results
    WHERE scope = 'create_session'
      AND (
          instr(response_json, 'participant_credentials') > 0
          OR instr(response_json, 'participant_token') > 0
      );
    """,
    """
    CREATE TABLE npc_render_jobs (
        session_id TEXT NOT NULL,
        intent_revision INTEGER NOT NULL,
        render_id TEXT NOT NULL UNIQUE,
        npc_participant_id TEXT NOT NULL,
        response_participant_id TEXT NOT NULL,
        command_scope TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        plan_json TEXT NOT NULL,
        prior_actions_json TEXT NOT NULL,
        npc_action_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending', 'delivered')),
        renderer_metadata_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        delivered_at TEXT,
        PRIMARY KEY (session_id, intent_revision),
        UNIQUE (command_scope, idempotency_key),
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
        FOREIGN KEY (npc_participant_id) REFERENCES participants(id),
        FOREIGN KEY (response_participant_id) REFERENCES participants(id)
    );

    CREATE INDEX idx_npc_render_jobs_pending
    ON npc_render_jobs(session_id, status);
    """,
    """
    ALTER TABLE npc_render_jobs ADD COLUMN render_started_at TEXT;
    """,
    """
    CREATE TABLE training_checkpoints (
        session_id TEXT NOT NULL REFERENCES sessions(id),
        revision INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL,
        PRIMARY KEY(session_id, revision)
    );
    CREATE TABLE training_reviews (
        session_id TEXT PRIMARY KEY REFERENCES sessions(id),
        participant_id TEXT NOT NULL REFERENCES participants(id),
        source_revision INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending', 'complete', 'unavailable')),
        result_json TEXT NOT NULL DEFAULT '{}',
        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
    );
    """,
    """
    CREATE TABLE training_rewinds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        root_session_id TEXT NOT NULL REFERENCES sessions(id),
        source_session_id TEXT NOT NULL REFERENCES sessions(id),
        child_session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id),
        source_revision INTEGER NOT NULL,
        owner_role TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX idx_training_rewinds_root
    ON training_rewinds(root_session_id, id);
    """,
)


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self, scenarios: list[CompiledScenario]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {
                int(row["version"])
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for version, migration in enumerate(MIGRATIONS, start=1):
                if version in applied:
                    continue
                connection.executescript(migration)
                connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))

        with self.write_transaction() as connection:
            for compiled in scenarios:
                existing = connection.execute(
                    "SELECT content_digest FROM scenario_versions "
                    "WHERE scenario_id = ? AND version = ?",
                    (compiled.id, compiled.version),
                ).fetchone()
                if existing is not None:
                    if existing["content_digest"] != compiled.content_digest:
                        raise RuntimeError(
                            f"Immutable scenario {compiled.id} version {compiled.version} changed"
                        )
                    continue
                connection.execute(
                    """
                    INSERT INTO scenario_versions(
                        scenario_id, version, title, language, content_digest,
                        compiler_version, compiled_digest, source_json, public_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        compiled.id,
                        compiled.version,
                        compiled.source["title"],
                        compiled.source["language"],
                        compiled.content_digest,
                        compiled.compiler_version,
                        compiled.compiled_digest,
                        canonical_json(compiled.source),
                        canonical_json(compiled.public_metadata()),
                    ),
                )

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def write_transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def journal_mode(self) -> str:
        with self.read_connection() as connection:
            return str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()


def decode_json_row(row: sqlite3.Row, field: str) -> dict:
    return json.loads(row[field])
