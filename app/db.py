"""
SQLite-backed audit log.

Every inspection (allowed or blocked) gets written here, along with which
tier made the call and why. This is what powers the "post-hoc security
review" story: if something slips through, or if you want to see how often
each tier is firing, this table is the source of truth.

We use raw sqlite3 rather than an ORM on purpose here -- the schema is
small and stable, and it keeps the dependency footprint (and thing you have
to explain in an interview) minimal.

Schema changes go through app/migrations/*.sql, tracked in a
schema_migrations table, rather than editing a single inline CREATE TABLE
-- see run_migrations() below.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

from app.config import settings

DB_PATH = Path(settings.db_path)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _configure_connection(conn: sqlite3.Connection) -> None:
    """
    Applied to every connection, not just at init time.

    - WAL mode lets readers and a writer proceed concurrently instead of
      the default rollback-journal mode, which takes an exclusive lock for
      the whole duration of a write. This is what actually raises
      SQLite's practical concurrency ceiling for a single-instance
      deployment -- it does NOT make SQLite suitable for multiple
      concurrent *writer* processes (e.g. several uvicorn workers each
      with their own connection pool), which is still the point where you
      need Postgres.
    - busy_timeout makes a connection that *does* hit a lock retry for up
      to 5s instead of raising "database is locked" immediately, which
      absorbs the kind of brief write contention you get from bursty
      traffic without failing the request.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")


def run_migrations(db_path: Path = DB_PATH) -> list[str]:
    """
    Apply any .sql files in app/migrations/ that haven't been applied yet,
    in filename order (each is prefixed NNN_). Returns the names of
    migrations that were applied this call, mainly so tests/startup logs
    can report what happened.
    """
    conn = sqlite3.connect(db_path)
    applied_now: list[str] = []
    try:
        _configure_connection(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )
            """
        )
        conn.commit()

        already_applied = {
            row[0] for row in conn.execute("SELECT version FROM schema_migrations")
        }

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for path in migration_files:
            version = int(path.name.split("_", 1)[0])
            if version in already_applied:
                continue
            conn.executescript(path.read_text())
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, path.name, time.time()),
            )
            conn.commit()
            applied_now.append(path.name)
    finally:
        conn.close()
    return applied_now


def init_db(db_path: Path = DB_PATH) -> None:
    """Kept as the public entrypoint other modules/tests already call."""
    run_migrations(db_path)


@contextmanager
def get_conn(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _configure_connection(conn)
    try:
        yield conn
    finally:
        conn.close()


def write_audit_entry(
    *,
    agent_id: str,
    tool_name: str,
    decision: str,
    resolved_tier: str,
    confidence: float,
    reason: str,
    tier_results: list[dict],
    arguments: dict,
    latency_ms: float,
    db_path: Path = DB_PATH,
) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO audit_log (
                ts, agent_id, tool_name, decision, resolved_tier,
                confidence, reason, tier_results_json, arguments_json, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                agent_id,
                tool_name,
                decision,
                resolved_tier,
                confidence,
                reason,
                json.dumps(tier_results),
                json.dumps(arguments),
                latency_ms,
            ),
        )
        conn.commit()
        return cur.lastrowid


def fetch_recent(limit: int = 100, db_path: Path = DB_PATH) -> list[dict]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_stats(db_path: Path = DB_PATH) -> dict:
    with get_conn(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()["c"]
        blocked = conn.execute(
            "SELECT COUNT(*) AS c FROM audit_log WHERE decision = 'block'"
        ).fetchone()["c"]

        # Full funnel breakdown: for each tier, how many requests were
        # resolved there, split by decision. This is what powers the
        # dashboard's funnel visualization -- it shows the *whole* shape
        # of the pipeline (including how many requests each cheap tier
        # absorbed before ever reaching the judge model), not just where
        # blocks happened.
        tier_rows = conn.execute(
            """
            SELECT resolved_tier, decision, COUNT(*) AS c
            FROM audit_log
            GROUP BY resolved_tier, decision
            """
        ).fetchall()

        funnel: dict[str, dict[str, int]] = {}
        for row in tier_rows:
            tier = row["resolved_tier"]
            funnel.setdefault(tier, {"allow": 0, "block": 0})
            funnel[tier][row["decision"]] = row["c"]

        avg_latency = conn.execute(
            "SELECT AVG(latency_ms) AS a FROM audit_log"
        ).fetchone()["a"]

        judge_calls = funnel.get("llm_judge", {"allow": 0, "block": 0})
        judge_call_count = judge_calls["allow"] + judge_calls["block"]

        return {
            "total_inspections": total,
            "total_blocked": blocked,
            "block_rate": (blocked / total) if total else 0.0,
            "funnel_by_tier": funnel,
            "judge_call_count": judge_call_count,
            "judge_call_rate": (judge_call_count / total) if total else 0.0,
            "avg_latency_ms": avg_latency or 0.0,
        }
