"""Group file repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_group_file(
    group_id: int,
    uploaded_by_user_id: int,
    stored_subor: str,
    original_nazov: str,
    typ_suboru: str,
) -> int:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO group_files (
            group_id,
            uploaded_by_user_id,
            stored_subor,
            original_nazov,
            typ_suboru,
            uploaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (group_id, uploaded_by_user_id, stored_subor, original_nazov, typ_suboru, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_group_files(group_id: int) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            gf.id,
            gf.group_id,
            gf.uploaded_by_user_id,
            gf.stored_subor,
            gf.original_nazov,
            gf.typ_suboru,
            gf.uploaded_at,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM group_files gf
        JOIN users u ON u.id = gf.uploaded_by_user_id
        WHERE gf.group_id = ?
        ORDER BY gf.uploaded_at DESC, gf.id DESC
        """,
        (group_id,),
    ).fetchall()
    return list(rows)


def get_group_file_by_id(group_id: int, group_file_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT
            gf.id,
            gf.group_id,
            gf.uploaded_by_user_id,
            gf.stored_subor,
            gf.original_nazov,
            gf.typ_suboru,
            gf.uploaded_at,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM group_files gf
        JOIN users u ON u.id = gf.uploaded_by_user_id
        WHERE gf.group_id = ? AND gf.id = ?
        """,
        (group_id, group_file_id),
    ).fetchone()
