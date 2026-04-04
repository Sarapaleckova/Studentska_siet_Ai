"""Group repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def get_groups_for_user(user_id: int, search_query: str) -> list[Row]:
    database = get_db()
    search_value = f"%{search_query.strip().lower()}%"
    rows = database.execute(
        """
        SELECT
            g.id,
            g.nazov,
            g.popis,
            g.obrazok_url,
            g.je_sukromna,
            gm.status AS membership_status,
            COALESCE(member_counts.member_count, 0) AS member_count
        FROM groups_table g
        LEFT JOIN group_memberships gm
            ON gm.group_id = g.id
            AND gm.user_id = ?
        LEFT JOIN (
            SELECT group_id, COUNT(*) AS member_count
            FROM group_memberships
            WHERE status = 'member'
            GROUP BY group_id
        ) member_counts ON member_counts.group_id = g.id
        WHERE LOWER(g.nazov) LIKE ?
        ORDER BY g.nazov COLLATE NOCASE ASC
        """,
        (user_id, search_value),
    ).fetchall()
    return list(rows)


def get_group_by_id(group_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT
            g.id,
            g.nazov,
            g.popis,
            g.obrazok_url,
            g.je_sukromna,
            COALESCE(member_counts.member_count, 0) AS member_count
        FROM groups_table g
        LEFT JOIN (
            SELECT group_id, COUNT(*) AS member_count
            FROM group_memberships
            WHERE status = 'member'
            GROUP BY group_id
        ) member_counts ON member_counts.group_id = g.id
        WHERE g.id = ?
        """,
        (group_id,),
    ).fetchone()


def get_group_membership(group_id: int, user_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT id, group_id, user_id, status, requested_at, joined_at
        FROM group_memberships
        WHERE group_id = ? AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone()


def join_public_group(group_id: int, user_id: int) -> str:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    membership = get_group_membership(group_id, user_id)

    if membership is None:
        database.execute(
            """
            INSERT INTO group_memberships (group_id, user_id, status, requested_at, joined_at)
            VALUES (?, ?, 'member', ?, ?)
            """,
            (group_id, user_id, now, now),
        )
        database.commit()
        return 'joined'

    if membership['status'] == 'member':
        return 'already-member'

    database.execute(
        """
        UPDATE group_memberships
        SET status = 'member', joined_at = ?
        WHERE group_id = ? AND user_id = ?
        """,
        (now, group_id, user_id),
    )
    database.commit()
    return 'joined'


def request_private_group_membership(group_id: int, user_id: int) -> str:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    membership = get_group_membership(group_id, user_id)

    if membership is None:
        database.execute(
            """
            INSERT INTO group_memberships (group_id, user_id, status, requested_at, joined_at)
            VALUES (?, ?, 'pending', ?, '')
            """,
            (group_id, user_id, now),
        )
        database.commit()
        return 'requested'

    if membership['status'] == 'pending':
        return 'already-requested'

    return 'already-member'
