"""Profile repository functions."""

from sqlite3 import Row

from student_network.db import get_db


def create_empty_profile(user_id: int) -> None:
    database = get_db()
    database.execute(
        """
        INSERT OR IGNORE INTO user_profiles (user_id, skola, rocnik_studia, popis, profilova_fotka)
        VALUES (?, '', '', '', '')
        """,
        (user_id,),
    )
    database.commit()


def get_profile_by_user_id(user_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        "SELECT user_id, skola, rocnik_studia, popis, profilova_fotka FROM user_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()


def save_profile(user_id: int, skola: str, rocnik_studia: str, popis: str, profilova_fotka: str | None = None) -> None:
    database = get_db()
    if profilova_fotka is None:
        profile = get_profile_by_user_id(user_id)
        profilova_fotka = profile['profilova_fotka'] if profile else ''

    database.execute(
        """
        INSERT INTO user_profiles (user_id, skola, rocnik_studia, popis, profilova_fotka)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            skola = excluded.skola,
            rocnik_studia = excluded.rocnik_studia,
            popis = excluded.popis,
            profilova_fotka = excluded.profilova_fotka
        """,
        (user_id, skola, rocnik_studia, popis, profilova_fotka),
    )
    database.commit()
