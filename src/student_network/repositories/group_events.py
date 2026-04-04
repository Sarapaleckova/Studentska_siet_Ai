"""Group events and notifications repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def get_group_event_by_id(group_id: int, event_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT
            id,
            group_id,
            created_by_user_id,
            event_date,
            event_time,
            nazov,
            popis,
            created_at,
            updated_at
        FROM group_events
        WHERE group_id = ? AND id = ?
        """,
        (group_id, event_id),
    ).fetchone()


def get_group_events_for_month(group_id: int, year: int, month: int) -> list[Row]:
    database = get_db()
    month_prefix = f"{year:04d}-{month:02d}"
    rows = database.execute(
        """
        SELECT
            ge.id,
            ge.group_id,
            ge.created_by_user_id,
            ge.event_date,
            ge.event_time,
            ge.nazov,
            ge.popis,
            ge.created_at,
            ge.updated_at,
            u.meno AS actor_meno,
            u.priezvisko AS actor_priezvisko
        FROM group_events ge
        JOIN users u ON u.id = ge.created_by_user_id
        WHERE ge.group_id = ?
            AND ge.event_date LIKE ? || '%'
        ORDER BY ge.event_date ASC, ge.event_time ASC
        """,
        (group_id, month_prefix),
    ).fetchall()
    return list(rows)


def create_group_event(
    group_id: int,
    created_by_user_id: int,
    event_date: str,
    event_time: str,
    nazov: str,
    popis: str,
) -> int:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO group_events (
            group_id,
            created_by_user_id,
            event_date,
            event_time,
            nazov,
            popis,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (group_id, created_by_user_id, event_date, event_time, nazov, popis, now, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def update_group_event(
    group_id: int,
    event_id: int,
    event_date: str,
    event_time: str,
    nazov: str,
    popis: str,
) -> None:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    database.execute(
        """
        UPDATE group_events
        SET event_date = ?, event_time = ?, nazov = ?, popis = ?, updated_at = ?
        WHERE group_id = ? AND id = ?
        """,
        (event_date, event_time, nazov, popis, now, group_id, event_id),
    )
    database.commit()


def delete_group_event(group_id: int, event_id: int) -> None:
    database = get_db()
    database.execute(
        "DELETE FROM group_events WHERE group_id = ? AND id = ?",
        (group_id, event_id),
    )
    database.commit()


def create_group_event_notification(
    group_id: int,
    event_id: int | None,
    actor_user_id: int,
    action_type: str,
    message: str,
) -> None:
    database = get_db()
    database.execute(
        """
        INSERT INTO group_event_notifications (
            group_id,
            event_id,
            actor_user_id,
            action_type,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            group_id,
            event_id,
            actor_user_id,
            action_type,
            message,
            datetime.utcnow().isoformat(timespec='seconds'),
        ),
    )
    database.commit()


def get_group_notifications(group_id: int, limit: int = 40) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            n.id,
            n.group_id,
            n.event_id,
            n.actor_user_id,
            n.action_type,
            n.message,
            n.created_at,
            u.meno AS actor_meno,
            u.priezvisko AS actor_priezvisko,
            ge.event_date,
            ge.event_time,
            ge.nazov AS event_nazov
        FROM group_event_notifications n
        JOIN users u ON u.id = n.actor_user_id
        LEFT JOIN group_events ge ON ge.id = n.event_id
        WHERE n.group_id = ?
        ORDER BY n.id DESC
        LIMIT ?
        """,
        (group_id, limit),
    ).fetchall()
    return list(rows)
