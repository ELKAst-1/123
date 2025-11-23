# database.py
import aiosqlite
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path("tasks.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_user_id INTEGER UNIQUE,
                full_name TEXT NOT NULL,
                tg_username TEXT,
                phone TEXT,
                is_admin BOOLEAN DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                practice_name TEXT,
                start_date DATE,
                end_date DATE NOT NULL,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                status TEXT CHECK(status IN ('ещё не смотрел', 'в работе', 'просмотренно', 'готово')),
                next_reminder DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        await db.execute(
            "INSERT OR IGNORE INTO users (tg_user_id, full_name, is_admin) VALUES (?, ?, ?)",
            (5016152706, "Администратор", 1)
        )
        await db.commit()

# === Новые функции для админки ===

async def get_or_create_user_by_full_name(full_name: str, tg_username: str = None, phone: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM users WHERE full_name = ?", (full_name,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row["id"]
        await db.execute(
            "INSERT INTO users (full_name, tg_username, phone) VALUES (?, ?, ?)",
            (full_name, tg_username, phone)
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE full_name = ?", (full_name,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_user_tasks_by_full_name(full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.id, t.practice_name, t.description, t.end_date, t.status, t.next_reminder
            FROM tasks t
            JOIN users u ON t.user_id = u.id
            WHERE u.full_name = ?
        """, (full_name,)) as cursor:
            return await cursor.fetchall()

async def update_task_reminder(task_id: int, reminder_dt: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET next_reminder = ? WHERE id = ?",
            (reminder_dt, task_id)
        )
        await db.commit()

async def task_exists(user_id: int, practice_name: str, description: str, end_date: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        if practice_name is not None:
            query = """
                SELECT 1 FROM tasks 
                WHERE user_id = ? AND end_date = ? AND practice_name = ? AND description = ?
            """
            params = (user_id, end_date, practice_name, description)
        else:
            query = """
                SELECT 1 FROM tasks 
                WHERE user_id = ? AND end_date = ? AND practice_name IS NULL AND description = ?
            """
            params = (user_id, end_date, description)
        async with db.execute(query, params) as cursor:
            return await cursor.fetchone() is not None

async def add_tasks_from_excel(tasks: List[dict]) -> int:
    from datetime import datetime, timedelta
    count = 0
    for task in tasks:
        user_id = await get_or_create_user_by_full_name(
            task["full_name"],
            task.get("tg_username"),
            task.get("phone")
        )
        if not user_id:
            continue
        exists = await task_exists(
            user_id,
            task.get("practice_name"),
            task["description"],
            task["end_date"]
        )
        if exists:
            continue
        end_dt = datetime.strptime(task["end_date"], "%Y-%m-%d")
        first_reminder = end_dt - timedelta(days=7)
        next_reminder = first_reminder.strftime("%Y-%m-%d 09:00:00")
        await create_task(
            practice_name=task.get("practice_name"),
            start_date=task.get("start_date"),
            end_date=task["end_date"],
            user_id=user_id,
            description=task["description"],
            status="ещё не смотрел",
            next_reminder=next_reminder
        )
        count += 1
    return count

# === Остальные функции ===

async def wipe_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks")
        await db.commit()

async def wipe_users_except_admin():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE tg_user_id != ?", (5016152706,))
        await db.commit()

async def get_user_by_full_name(full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, tg_user_id, is_admin FROM users WHERE full_name = ?", (full_name,)) as cursor:
            return await cursor.fetchall()

async def set_user_admin(tg_user_id: int, is_admin: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin = ? WHERE tg_user_id = ?", (1 if is_admin else 0, tg_user_id))
        await db.commit()

async def get_all_tasks_for_export():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT 
                t.practice_name,
                t.start_date,
                t.end_date,
                u.full_name,
                u.tg_username,
                u.phone,
                t.description AS task_description,
                t.status,
                t.next_reminder
            FROM tasks t
            JOIN users u ON t.user_id = u.id
        """) as cursor:
            return await cursor.fetchall()

async def get_tasks_by_user_id(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()

async def get_user_by_tg_id(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_user_id = ?", (tg_id,)) as cursor:
            return await cursor.fetchone()

async def create_user(tg_id: int, full_name: str, username: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (tg_user_id, full_name, tg_username) VALUES (?, ?, ?)",
            (tg_id, full_name, username)
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE tg_user_id = ?", (tg_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def create_task(**kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        query = f"INSERT INTO tasks ({columns}) VALUES ({placeholders})"
        await db.execute(query, tuple(kwargs.values()))
        await db.commit()