"""User repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db
from student_network.repositories.profiles import create_empty_profile


def create_user(meno: str, priezvisko: str, email: str, heslo: str) -> int:
    database = get_db()
    cursor = database.execute(
        """
        INSERT INTO users (meno, priezvisko, email, heslo, datum_vytvorenia_uctu)
        VALUES (?, ?, ?, ?, ?)
        """,
        (meno, priezvisko, email, heslo, datetime.utcnow().isoformat(timespec='seconds')),
    )
    database.commit()
    user_id = int(cursor.lastrowid)
    create_empty_profile(user_id)
    return user_id


def get_user_by_email(email: str) -> Row | None:
    database = get_db()
    return database.execute(
        "SELECT id, meno, priezvisko, email, heslo, datum_vytvorenia_uctu FROM users WHERE email = ?",
        (email,),
    ).fetchone()


def get_user_by_id(user_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        "SELECT id, meno, priezvisko, email, heslo, datum_vytvorenia_uctu FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def update_user_name(user_id: int, meno: str, priezvisko: str) -> None:
    database = get_db()
    database.execute(
        "UPDATE users SET meno = ?, priezvisko = ? WHERE id = ?",
        (meno, priezvisko, user_id),
    )
    database.commit()


def search_users_by_name(search_query: str) -> list[Row]:
    database = get_db()
    search_value = f"%{search_query.strip().lower()}%"
    rows = database.execute(
        """
        SELECT
            u.id,
            u.meno,
            u.priezvisko,
            u.email,
            up.profilova_fotka
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE
            LOWER(u.meno) LIKE ?
            OR LOWER(u.priezvisko) LIKE ?
            OR LOWER(u.meno || ' ' || u.priezvisko) LIKE ?
            OR LOWER(u.email) LIKE ?
        ORDER BY u.priezvisko COLLATE NOCASE ASC, u.meno COLLATE NOCASE ASC
        """,
        (search_value, search_value, search_value, search_value),
    ).fetchall()
    return list(rows)
