"""Repository for private (direct) messages between users."""
from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_private_message(sender_id: int, recipient_id: int, content: str) -> int:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO private_messages (sender_id, recipient_id, content, is_read, created_at)
        VALUES (?, ?, ?, 0, ?)
        """,
        (sender_id, recipient_id, content, datetime.utcnow().isoformat(sep=' ', timespec='seconds')),
    )
    db.commit()
    return int(cursor.lastrowid)


def get_messages_for_user(user_id: int) -> list[Row]:
    db = get_db()
    rows = db.execute(
        """
        SELECT pm.id, pm.sender_id, pm.recipient_id, pm.content, pm.is_read, pm.created_at,
               su.meno AS sender_meno, su.priezvisko AS sender_priezvisko,
               ru.meno AS recipient_meno, ru.priezvisko AS recipient_priezvisko
        FROM private_messages pm
        LEFT JOIN users su ON su.id = pm.sender_id
        LEFT JOIN users ru ON ru.id = pm.recipient_id
        WHERE pm.sender_id = ? OR pm.recipient_id = ?
        ORDER BY pm.created_at DESC
        """,
        (user_id, user_id),
    ).fetchall()
    return list(rows)


def get_unread_count(user_id: int) -> int:
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS cnt FROM private_messages WHERE recipient_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()
    return int(row['cnt'] or 0) if row is not None else 0


def mark_message_read(message_id: int, recipient_id: int) -> bool:
    db = get_db()
    # Only recipient can mark as read
    db.execute(
        "UPDATE private_messages SET is_read = 1 WHERE id = ? AND recipient_id = ?",
        (message_id, recipient_id),
    )
    db.commit()
    return True


def get_message_by_id(message_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM private_messages WHERE id = ?",
        (message_id,),
    ).fetchone()
