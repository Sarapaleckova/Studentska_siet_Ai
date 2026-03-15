"""Profile repository functions."""

from sqlite3 import Row

from student_network.db import get_db


def create_empty_profile(user_id: int) -> None:
    database = get_db()
    database.execute(
        """
        INSERT OR IGNORE INTO user_profiles (user_id, skola, rocnik_studia, popis)
        VALUES (?, '', '', '')
        """,
        (user_id,),
    )
    database.commit()


def get_profile_by_user_id(user_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        "SELECT user_id, skola, rocnik_studia, popis FROM user_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()


def save_profile(user_id: int, skola: str, rocnik_studia: str, popis: str) -> None:
    database = get_db()
    database.execute(
        """
        INSERT INTO user_profiles (user_id, skola, rocnik_studia, popis)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            skola = excluded.skola,
            rocnik_studia = excluded.rocnik_studia,
            popis = excluded.popis
        """,
        (user_id, skola, rocnik_studia, popis),
    )
    database.commit()
