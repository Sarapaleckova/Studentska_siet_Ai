"""Post repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_post(
    author_id: int,
    nazov: str,
    popis: str,
    nahladovy_obrazok: str,
    subor: str,
    subor_povodny_nazov: str,
) -> int:
    database = get_db()
    cursor = database.execute(
        """
        INSERT INTO posts (
            author_id,
            nazov,
            popis,
            nahladovy_obrazok,
            subor,
            subor_povodny_nazov,
            datum_vytvorenia
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            author_id,
            nazov,
            popis,
            nahladovy_obrazok,
            subor,
            subor_povodny_nazov,
            datetime.utcnow().isoformat(timespec='seconds'),
        ),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_all_posts() -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            p.id,
            p.author_id,
            p.nazov,
            p.popis,
            p.nahladovy_obrazok,
            p.subor,
            p.subor_povodny_nazov,
            p.datum_vytvorenia,
            COALESCE(r.average_rating, 0) AS average_rating,
            COALESCE(r.rating_count, 0) AS rating_count,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM posts p
        JOIN users u ON u.id = p.author_id
        LEFT JOIN (
            SELECT
                post_id,
                AVG(rating) AS average_rating,
                COUNT(*) AS rating_count
            FROM post_ratings
            GROUP BY post_id
        ) r ON r.post_id = p.id
        ORDER BY p.id DESC
        """
    ).fetchall()
    return list(rows)


def get_post_by_id(post_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT
            p.id,
            p.author_id,
            p.nazov,
            p.popis,
            p.nahladovy_obrazok,
            p.subor,
            p.subor_povodny_nazov,
            p.datum_vytvorenia,
            COALESCE(r.average_rating, 0) AS average_rating,
            COALESCE(r.rating_count, 0) AS rating_count,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM posts p
        JOIN users u ON u.id = p.author_id
        LEFT JOIN (
            SELECT
                post_id,
                AVG(rating) AS average_rating,
                COUNT(*) AS rating_count
            FROM post_ratings
            GROUP BY post_id
        ) r ON r.post_id = p.id
        WHERE p.id = ?
        """,
        (post_id,),
    ).fetchone()


def get_posts_by_author_id(author_id: int) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            p.id,
            p.nazov,
            p.datum_vytvorenia,
            p.nahladovy_obrazok
        FROM posts p
        WHERE p.author_id = ?
        ORDER BY p.id DESC
        """,
        (author_id,),
    ).fetchall()
    return list(rows)
