"""Profile repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_empty_profile(user_id: int) -> None:
    database = get_db()
    database.execute(
        """
        INSERT OR IGNORE INTO user_profiles (
            user_id,
            skola,
            rocnik_studia,
            popis,
            profilova_fotka,
            theme_preset,
            theme_bg_color,
            theme_nav_color,
            theme_bg_image
        )
        VALUES (?, '', '', '', '', 'default', '#0b1f4d', '#071433', '')
        """,
        (user_id,),
    )
    database.commit()


def get_profile_by_user_id(user_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT
            user_id,
            skola,
            rocnik_studia,
            popis,
            profilova_fotka,
            theme_preset,
            theme_bg_color,
            theme_nav_color,
            theme_bg_image
        FROM user_profiles
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


def save_profile(
    user_id: int,
    skola: str,
    rocnik_studia: str,
    popis: str,
    profilova_fotka: str | None = None,
    theme_preset: str = 'default',
    theme_bg_color: str = '#0b1f4d',
    theme_nav_color: str = '#071433',
    theme_bg_image: str | None = None,
) -> None:
    database = get_db()
    profile = get_profile_by_user_id(user_id)
    if profilova_fotka is None:
        profilova_fotka = profile['profilova_fotka'] if profile else ''

    if theme_bg_image is None:
        theme_bg_image = profile['theme_bg_image'] if profile else ''

    database.execute(
        """
        INSERT INTO user_profiles (
            user_id,
            skola,
            rocnik_studia,
            popis,
            profilova_fotka,
            theme_preset,
            theme_bg_color,
            theme_nav_color,
            theme_bg_image
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            skola = excluded.skola,
            rocnik_studia = excluded.rocnik_studia,
            popis = excluded.popis,
            profilova_fotka = excluded.profilova_fotka,
            theme_preset = excluded.theme_preset,
            theme_bg_color = excluded.theme_bg_color,
            theme_nav_color = excluded.theme_nav_color,
            theme_bg_image = excluded.theme_bg_image
        """,
        (
            user_id,
            skola,
            rocnik_studia,
            popis,
            profilova_fotka,
            theme_preset,
            theme_bg_color,
            theme_nav_color,
            theme_bg_image,
        ),
    )
    database.commit()


def get_user_additional_emails(user_id: int) -> list[str]:
    database = get_db()
    rows = database.execute(
        """
        SELECT email
        FROM user_additional_emails
        WHERE user_id = ?
        ORDER BY email COLLATE NOCASE ASC
        """,
        (user_id,),
    ).fetchall()
    return [str(row['email']) for row in rows]


def replace_user_additional_emails(user_id: int, emails: list[str]) -> None:
    database = get_db()
    database.execute(
        "DELETE FROM user_additional_emails WHERE user_id = ?",
        (user_id,),
    )

    now = datetime.utcnow().isoformat(timespec='seconds')
    for email in emails:
        database.execute(
            """
            INSERT INTO user_additional_emails (user_id, email, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, email, now),
        )

    database.commit()
