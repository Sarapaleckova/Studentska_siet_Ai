"""Group board repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_group_board_post(
    group_id: int,
    author_user_id: int,
    board_type: str,
    title: str,
    content: str,
) -> int:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO group_board_posts (
            group_id,
            author_user_id,
            board_type,
            title,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (group_id, author_user_id, board_type, title, content, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def update_group_board_post(post_id: int, title: str, content: str) -> None:
    database = get_db()
    database.execute(
        """
        UPDATE group_board_posts
        SET
            title = ?,
            content = ?
        WHERE id = ?
        """,
        (title, content, post_id),
    )
    database.commit()


def get_group_board_posts(group_id: int, board_type: str) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            gbp.id,
            gbp.group_id,
            gbp.author_user_id,
            gbp.board_type,
            gbp.title,
            gbp.content,
            gbp.created_at,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM group_board_posts gbp
        JOIN users u ON u.id = gbp.author_user_id
        WHERE gbp.group_id = ? AND gbp.board_type = ?
        ORDER BY gbp.created_at DESC, gbp.id DESC
        """,
        (group_id, board_type),
    ).fetchall()
    return list(rows)
