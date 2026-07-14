"""
Issued, revocable API keys, backed by the api_keys table (migration 002).

Design:
  - A raw key is only ever shown once, at creation time (same pattern as
    GitHub PATs / Stripe secret keys). We store only its SHA-256 hash.
  - SHA-256 (not bcrypt/argon2) is deliberate here: these are
    high-entropy, randomly generated tokens (32 bytes from
    secrets.token_urlsafe), not user-chosen passwords, so there's no
    brute-force-by-guessing risk to defend against with a slow hash --
    the entropy is in the token itself. A fast hash keeps auth checks
    cheap on every request.
  - Revocation is a soft delete (revoked_at timestamp) so the audit trail
    of who had access when is preserved, rather than deleting the row.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from pathlib import Path

from app.db import get_conn, DB_PATH

KEY_PREFIX = "gp_"  # "guardrail proxy" -- makes issued keys recognizable in logs/diffs


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_key(name: str, db_path: Path = DB_PATH) -> dict:
    """
    Creates a new key and returns it, INCLUDING the raw value. This is the
    only time the raw value is ever available -- callers must save it
    immediately.
    """
    raw_key = KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)

    with get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO api_keys (key_hash, name, created_at, revoked_at) VALUES (?, ?, ?, NULL)",
            (key_hash, name, time.time()),
        )
        conn.commit()
        return {"id": cur.lastrowid, "name": name, "api_key": raw_key}


def verify_key(raw_key: str, db_path: Path = DB_PATH) -> bool:
    key_hash = _hash_key(raw_key)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (key_hash,),
        ).fetchone()
        return row is not None


def list_keys(db_path: Path = DB_PATH) -> list[dict]:
    """Never returns the hash or raw key -- just metadata for the admin view."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, revoked_at FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def revoke_key(key_id: int, db_path: Path = DB_PATH) -> bool:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (time.time(), key_id),
        )
        conn.commit()
        return cur.rowcount > 0
