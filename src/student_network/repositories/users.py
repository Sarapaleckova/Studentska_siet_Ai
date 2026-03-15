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
