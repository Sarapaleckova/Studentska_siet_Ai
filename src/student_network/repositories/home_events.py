"""Home event board repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_home_event(created_by_user_id: int, nazov: str, event_at: str, kategoria: str) -> int:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO home_events (created_by_user_id, nazov, event_at, kategoria, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (created_by_user_id, nazov, event_at, kategoria, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_home_events_with_visibility_for_user(user_id: int) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            he.id,
            he.created_by_user_id,
            he.nazov,
            he.event_at,
            he.kategoria,
            he.created_at,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko,
            COALESCE(hp.is_hidden, 0) AS is_hidden
        FROM home_events he
        JOIN users u ON u.id = he.created_by_user_id
        LEFT JOIN home_event_hidden_preferences hp
            ON hp.event_id = he.id AND hp.user_id = ?
        ORDER BY he.event_at ASC, he.id ASC
        """,
        (user_id,),
    ).fetchall()
    return list(rows)


def get_home_event_by_id(event_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT id, created_by_user_id, nazov, event_at, kategoria, created_at
        FROM home_events
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()


def set_home_event_hidden_for_user(user_id: int, event_id: int, is_hidden: bool) -> None:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    database.execute(
        """
        INSERT INTO home_event_hidden_preferences (user_id, event_id, is_hidden, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, event_id)
        DO UPDATE SET
            is_hidden = excluded.is_hidden,
            updated_at = excluded.updated_at
        """,
        (user_id, event_id, 1 if is_hidden else 0, now),
    )
    database.commit()
