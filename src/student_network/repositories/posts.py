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
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM posts p
        JOIN users u ON u.id = p.author_id
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
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM posts p
        JOIN users u ON u.id = p.author_id
        WHERE p.id = ?
        """,
        (post_id,),
    ).fetchone()
