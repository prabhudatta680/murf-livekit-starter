import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional, TypedDict

# Creates callers.db in the same folder as this file if it doesn't exist yet
DB_PATH = os.path.join(os.path.dirname(__file__), "callers.db")


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates the callers table if it doesn't already exist. Call this once on startup."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS callers (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            language_preference TEXT,
            facts TEXT,              -- stored as a JSON string, e.g. '{"crops":"cotton","land_size":"5 acres"}'
            last_interaction TEXT    -- ISO timestamp string
        )
        """
    )
    conn.commit()
    conn.close()


class CallerRecord(TypedDict):
    user_id: str
    name: str
    language_preference: str
    facts: dict
    last_interaction: str


def lookup_caller(user_id: str) -> Optional[CallerRecord]:
    """
    Looks up a caller by user_id.
    Returns the record (with facts parsed back into a dict) or None if not found.
    """
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM callers WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "language_preference": row["language_preference"],
        "facts": json.loads(row["facts"] or "{}"),
        "last_interaction": row["last_interaction"],
    }


def save_caller_info(
    user_id: str,
    name: str,
    new_facts: dict,
    language_preference: str = "en",
) -> None:
    """
    Saves or updates a caller's info. Call this only AFTER the caller has
    given explicit consent to be remembered (see Day 4, Step 5).
    Merges new facts with any existing facts rather than overwriting them.
    """
    existing = lookup_caller(user_id)
    merged_facts = {**(existing["facts"] if existing else {}), **new_facts}

    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO callers (user_id, name, language_preference, facts, last_interaction)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name = excluded.name,
            language_preference = excluded.language_preference,
            facts = excluded.facts,
            last_interaction = excluded.last_interaction
        """,
        (
            user_id,
            name,
            language_preference,
            json.dumps(merged_facts),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


# Make sure the table exists as soon as this module is imported
init_db()
