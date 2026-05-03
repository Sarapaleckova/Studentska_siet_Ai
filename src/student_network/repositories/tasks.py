"""Task repository functions."""

from datetime import datetime
from typing import Optional
from sqlite3 import Row

from student_network.db import get_db


def create_task(
    user_id: int,
    text: str,
    deadline: Optional[str] = None,
) -> int:
    """Create a new task."""
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO user_tasks (
            user_id,
            text,
            is_completed,
            deadline,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, text, 0, deadline, now, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_task_by_id(task_id: int) -> Optional[Row]:
    """Get a task by ID."""
    database = get_db()
    return database.execute(
        "SELECT * FROM user_tasks WHERE id = ?",
        (task_id,),
    ).fetchone()


def get_tasks_for_user(user_id: int, include_completed: bool = True) -> list[Row]:
    """Get all tasks for a user."""
    database = get_db()
    if include_completed:
        return database.execute(
            """
            SELECT * FROM user_tasks
            WHERE user_id = ?
            ORDER BY is_completed ASC, created_at DESC
            """,
            (user_id,),
        ).fetchall()
    else:
        return database.execute(
            """
            SELECT * FROM user_tasks
            WHERE user_id = ? AND is_completed = 0
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()


def update_task(
    task_id: int,
    text: Optional[str] = None,
    is_completed: Optional[int] = None,
    deadline: Optional[str] = None,
) -> bool:
    """Update a task."""
    database = get_db()
    task = get_task_by_id(task_id)
    if task is None:
        return False

    current_text = task['text'] if text is None else text
    current_completed = task['is_completed'] if is_completed is None else is_completed
    current_deadline = task['deadline'] if deadline is None else deadline
    now = datetime.utcnow().isoformat(timespec='seconds')

    database.execute(
        """
        UPDATE user_tasks
        SET text = ?, is_completed = ?, deadline = ?, updated_at = ?
        WHERE id = ?
        """,
        (current_text, current_completed, current_deadline, now, task_id),
    )
    database.commit()
    return True


def delete_task(task_id: int) -> bool:
    """Delete a task."""
    database = get_db()
    cursor = database.execute(
        "DELETE FROM user_tasks WHERE id = ?",
        (task_id,),
    )
    database.commit()
    return cursor.rowcount > 0


def toggle_task_completion(task_id: int) -> bool:
    """Toggle the completion status of a task."""
    database = get_db()
    task = get_task_by_id(task_id)
    if task is None:
        return False

    new_status = 1 - task['is_completed']
    now = datetime.utcnow().isoformat(timespec='seconds')
    database.execute(
        """
        UPDATE user_tasks
        SET is_completed = ?, updated_at = ?
        WHERE id = ?
        """,
        (new_status, now, task_id),
    )
    database.commit()
    return True
