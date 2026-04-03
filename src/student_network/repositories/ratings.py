"""Post rating repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def upsert_post_rating(post_id: int, user_id: int, rating: int) -> None:
    database = get_db()
    database.execute(
        """
        INSERT INTO post_ratings (post_id, user_id, rating, rated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(post_id, user_id) DO UPDATE SET
            rating = excluded.rating,
            rated_at = excluded.rated_at
        """,
        (post_id, user_id, rating, datetime.utcnow().isoformat(timespec='seconds')),
    )
    database.commit()


def get_user_post_rating(post_id: int, user_id: int) -> int | None:
    database = get_db()
    row = database.execute(
        "SELECT rating FROM post_ratings WHERE post_id = ? AND user_id = ?",
        (post_id, user_id),
    ).fetchone()
    return int(row['rating']) if row else None


def get_post_rating_summary(post_id: int) -> Row:
    database = get_db()
    row = database.execute(
        """
        SELECT
            AVG(rating) AS average_rating,
            COUNT(*) AS rating_count
        FROM post_ratings
        WHERE post_id = ?
        """,
        (post_id,),
    ).fetchone()
    return row
