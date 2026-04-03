"""Post comment repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_post_comment(post_id: int, user_id: int, text: str, parent_comment_id: int | None = None) -> int:
    database = get_db()
    cursor = database.execute(
        """
        INSERT INTO post_comments (post_id, user_id, parent_comment_id, text, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (post_id, user_id, parent_comment_id, text, datetime.utcnow().isoformat(timespec='seconds')),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_post_comments(post_id: int) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            c.id,
            c.post_id,
            c.user_id,
            c.parent_comment_id,
            c.text,
            c.created_at,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM post_comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC, c.id ASC
        """,
        (post_id,),
    ).fetchall()
    return list(rows)


def get_post_comment_by_id(post_id: int, comment_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT id, post_id, user_id, parent_comment_id, text, created_at
        FROM post_comments
        WHERE post_id = ? AND id = ?
        """,
        (post_id, comment_id),
    ).fetchone()
