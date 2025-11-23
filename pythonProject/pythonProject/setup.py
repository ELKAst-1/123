#!/usr/bin/env python3
import os
import sys
import sqlite3
from pathlib import Path

BOT_ADMIN_ID = 5016152706
PROJECT_ROOT = Path.cwd()

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")  # Убираем лишние переносы

def create_files():
    print("📝 Генерация файлов проекта...")

    # .env
    write_file(PROJECT_ROOT / ".env", f"BOT_TOKEN=YOUR_BOT_TOKEN_HERE\nADMIN_ID={BOT_ADMIN_ID}\nTIMEZONE=Europe/Moscow")

    # requirements.txt
    write_file(PROJECT_ROOT / "requirements.txt",
"""aiogram==3.12.0
python-dotenv==1.0.1
APScheduler==3.10.4
openpyxl==3.15.0
tzlocal==5.2
""")

    # handlers/__init__.py
    write_file(PROJECT_ROOT / "handlers/__init__.py", "")

    # utils/__init__.py
    write_file(PROJECT_ROOT / "utils/__init__.py", "")

    # main.py
    write_file(PROJECT_ROOT / "main.py",
"""import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tzlocal import get_localzone
from dotenv import load_dotenv
import os

from database import init_db
from handlers import register_all_handlers
from utils.scheduler import setup_scheduler

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в .env")

async def main():
    await init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    scheduler = AsyncIOScheduler(timezone=get_localzone())
    register_all_handlers(dp, bot)
    setup_scheduler(scheduler, bot)
    scheduler.start()
    print("✅ Бот запущен!")
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\\n🛑 Бот остановлен.")
""")

    # database.py
    write_file(PROJECT_ROOT / "database.py",
f'''import aiosqlite
from pathlib import Path

DB_PATH = Path("tasks.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_user_id INTEGER UNIQUE NOT NULL,
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
            ({BOT_ADMIN_ID}, "Администратор", 1)
        )
        await db.commit()

async def wipe_tasks():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks")
        await db.commit()

async def wipe_users_except_admin():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE tg_user_id != ?", ({BOT_ADMIN_ID},))
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
    async with aiosqlite.connect(DB_PATH) as db:
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        query = "INSERT INTO tasks (" + ", ".join(kwargs.keys()) + ") VALUES (" + ", ".join(["?"] * len(kwargs)) + ")"
        await db.execute(query, tuple(kwargs.values()))
        await db.commit()
''')

    # handlers/common.py
    write_file(PROJECT_ROOT / "handlers/common.py",
"""from aiogram import Router, F
from aiogram.types import Message
from database import get_user_by_tg_id
from handlers.user import show_user_menu

common_router = Router()

@common_router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = await get_user_by_tg_id(message.from_user.id)
    if user:
        await show_user_menu(message)
    else:
        await message.answer("👋 Добро пожаловать!\\nПожалуйста, введите ваше ФИО:")
        from handlers.user import RegisterStates
        await message.bot.send_message(message.chat.id, "Введите ФИО:")
        await message.answer("Пример: Иванов Иван Иванович")
        from aiogram.fsm.context import FSMContext
        state = FSMContext(storage=message.bot.session.storage, chat_id=message.chat.id, user_id=message.from_user.id)
        await state.set_state(RegisterStates.waiting_for_name)

def register_common_handlers(dp):
    dp.include_router(common_router)
""")

    # handlers/user.py
    write_file(PROJECT_ROOT / "handlers/user.py",
"""from aiogram import Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_user_by_tg_id, create_user, get_tasks_by_user_id

user_router = Router()

class RegisterStates(StatesGroup):
    waiting_for_name = State()

# --- Регистрация ---
@user_router.message(RegisterStates.waiting_for_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("❌ Пожалуйста, введите полное ФИО (минимум имя и фамилия).")
        return
    await create_user(message.from_user.id, full_name, message.from_user.username)
    await state.clear()
    await show_user_menu(message)

# --- Меню ---
async def show_user_menu(message: Message):
    kb = [[KeyboardButton(text="📋 Мои задачи")]]
    await message.answer(
        "✅ Вы зарегистрированы!\\nВыберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )

# --- Задачи ---
@user_router.message(F.text == "📋 Мои задачи")
async def show_tasks(message: Message):
    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        return
    tasks = await get_tasks_by_user_id(user["id"])
    if not tasks:
        await message.answer("📭 У вас пока нет задач.")
        return
    for task in tasks:
        txt = (
            f"📄 <b>Практика:</b> {task['practice_name'] or task['description']}\\n"
            f"📅 <b>До:</b> {task['end_date']}\\n"
            f"📝 <b>Статус:</b> {task['status']}\\n"
            f"💬 <b>Описание:</b> {task['description']}"
        )
        await message.answer(txt, parse_mode="HTML")

def register_user_handlers(dp):
    dp.include_router(user_router)
""")

    # handlers/admin.py
    write_file(PROJECT_ROOT / "handlers/admin.py",
f"""from aiogram import Router, F, types
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    get_user_by_full_name, set_user_admin, wipe_tasks, wipe_users_except_admin,
    get_all_tasks_for_export
)
from utils.excel import export_tasks_to_excel
import os

admin_router = Router()

async def is_admin(tg_id: int) -> bool:
    from database import get_user_by_tg_id
    user = await get_user_by_tg_id(tg_id)
    return bool(user and user["is_admin"])

@admin_router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    kb = [
        [KeyboardButton(text="📥 Выгрузить все задачи")],
        [KeyboardButton(text="👑 Назначить/удалить админа")],
        [KeyboardButton(text="🧹 Очистить БД")]
    ]
    await message.answer("Панель администратора:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

class AdminManageStates(StatesGroup):
    waiting_name = State()
    waiting_confirm = State()

@admin_router.message(F.text == "👑 Назначить/удалить админа")
async def start_admin_manage(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("Введите ФИО пользователя:")
    await state.set_state(AdminManageStates.waiting_name)

@admin_router.message(AdminManageStates.waiting_name)
async def handle_admin_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    users = await get_user_by_full_name(full_name)
    if not users:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        return
    if len(users) > 1:
        details = "\\n".join([f"• TG ID: {{u[1]}}, админ: {{'да' if u[2] else 'нет'}}" for u in users])
        await message.answer(f"⚠️ Найдено несколько пользователей:\\n{{details}}\\n\\nУточните ФИО.")
        await state.clear()
        return
    user_id, tg_id, is_adm = users[0]
    action = "удалить из админов" if is_adm else "назначить админом"
    await state.update_data(tg_id=tg_id, is_adm=is_adm, full_name=full_name)
    await message.answer(f"Пользователь: <b>{{full_name}}</b>\\nТекущий статус: {{'админ' if is_adm else 'обычный'}}\\n\\nПодтвердите: {{action}}? (да/нет)", parse_mode="HTML")
    await state.set_state(AdminManageStates.waiting_confirm)

@admin_router.message(AdminManageStates.waiting_confirm)
async def confirm_admin_change(message: Message, state: FSMContext):
    if message.text.lower() not in ("да", "yes", "y"):
        await message.answer("❌ Отменено.")
        await state.clear()
        return
    data = await state.get_data()
    new_status = not data["is_adm"]
    await set_user_admin(data["tg_id"], new_status)
    status_txt = "назначен админом" if new_status else "лишён прав админа"
    await message.answer(f"✅ Пользователь {{data['full_name']}} {{status_txt}}.")
    await state.clear()

@admin_router.message(F.text == "📥 Выгрузить все задачи")
async def export_all_tasks(message: Message):
    if not await is_admin(message.from_user.id):
        return
    tasks = await get_all_tasks_for_export()
    if not tasks:
        await message.answer("📭 Нет задач для выгрузки.")
        return
    filepath = export_tasks_to_excel(tasks)
    await message.answer_document(types.FSInputFile(filepath))
    os.remove(filepath)

class WipeStates(StatesGroup):
    confirm_tasks = State()
    confirm_users = State()

@admin_router.message(F.text == "🧹 Очистить БД")
async def start_wipe(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Подтвердите действия:\\n\\n1. Удалить ВСЕ задачи? (да/нет)")
    await state.set_state(WipeStates.confirm_tasks)

@admin_router.message(WipeStates.confirm_tasks)
async def confirm_wipe_tasks(message: Message, state: FSMContext):
    if message.text.lower() in ("да", "yes", "y"):
        await wipe_tasks()
        await message.answer("✅ Все задачи удалены.")
    else:
        await message.answer("⏭ Задачи сохранены.")
    await message.answer("2. Удалить всех пользователей, кроме админа? (да/нет)")
    await state.set_state(WipeStates.confirm_users)

@admin_router.message(WipeStates.confirm_users)
async def confirm_wipe_users(message: Message, state: FSMContext):
    if message.text.lower() in ("да", "yes", "y"):
        await wipe_users_except_admin()
        await message.answer("✅ Пользователи удалены. Админ сохранён.")
    else:
        await message.answer("⏭ Пользователи сохранены.")
    await state.clear()

def register_admin_handlers(dp):
    dp.include_router(admin_router)
""")

    # handlers/__init__.py (полная версия)
    write_file(PROJECT_ROOT / "handlers/__init__.py",
"""from aiogram import Dispatcher
from .common import register_common_handlers
from .user import register_user_handlers
from .admin import register_admin_handlers

def register_all_handlers(dp: Dispatcher, bot):
    register_common_handlers(dp)
    register_user_handlers(dp)
    register_admin_handlers(dp)
""")

    # utils/excel.py
    write_file(PROJECT_ROOT / "utils/excel.py",
"""from openpyxl import Workbook
import tempfile
import os

def export_tasks_to_excel(tasks):
    wb = Workbook()
    ws = wb.active
    ws.title = "Все задачи"
    headers = [
        "practice_name", "start_date", "end_date", "full_name",
        "tg_username", "phone", "task_description", "status", "next_reminder"
    ]
    ws.append(headers)
    for task in tasks:
        row = [
            task["practice_name"],
            task["start_date"],
            task["end_date"],
            task["full_name"],
            task["tg_username"] or "—",
            task["phone"] or "—",
            task["task_description"],
            task["status"],
            task["next_reminder"] or ""
        ]
        ws.append(row)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        wb.save(tmp.name)
        return tmp.name
""")

    #    # utils/scheduler.py
    write_file(PROJECT_ROOT / "utils/scheduler.py",
"""from apscheduler.triggers.cron import CronTrigger
from database import DB_PATH
import aiosqlite
from datetime import datetime, timedelta

async def send_reminders(bot):
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT t.id, t.description, t.end_date, t.status, u.tg_user_id
            FROM tasks t
            JOIN users u ON t.user_id = u.id
            WHERE t.next_reminder <= ? AND t.status != 'готово'
        ''', (now.strftime("%Y-%m-%d %H:%M:%S"),)) as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            task_id, desc, end_date, status, tg_id = row
            try:
                await bot.send_message(
                    tg_id,
                    f"🔔 <b>Напоминание о практике</b>\\n\\n"
                    f"Описание: {desc}\\n"
                    f"Срок: {end_date}\\n\\n"
                    f"Напоминание повторяется еженедельно, пока задача не будет отмечена как «готово».",
                    parse_mode="HTML"
                )
                next_rem = now + timedelta(weeks=1)
                await db.execute(
                    "UPDATE tasks SET next_reminder = ? WHERE id = ?",
                    (next_rem.strftime("%Y-%m-%d %H:%M:%S"), task_id)
                )
            except Exception as e:
                print(f"Не удалось отправить напоминание пользователю {tg_id}: {e}")
        await db.commit()

def setup_scheduler(scheduler, bot):
    scheduler.add_job(
        send_reminders,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="daily_reminders",
        replace_existing=True
    )
""")

    # README.md
    write_file(PROJECT_ROOT / "README.md",
f"""# 📋 Telegram-бот для управления практиками

**Админ по умолчанию:** `{BOT_ADMIN_ID}`

## Установка
```bash
python setup.py
# Затем отредактируйте .env → вставьте ваш BOT_TOKEN
pip install -r requirements.txt
python main.py
""")

def init_database():
    print("🗃 Инициализация базы данных...")
    db_path = PROJECT_ROOT / "tasks.db"
    if not db_path.exists():
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute('''
CREATE TABLE users (
id INTEGER PRIMARY KEY AUTOINCREMENT,
tg_user_id INTEGER UNIQUE NOT NULL,
full_name TEXT NOT NULL,
tg_username TEXT,
phone TEXT,
is_admin BOOLEAN DEFAULT 0
)
''')
        cur.execute('''
CREATE TABLE tasks (
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
''')
        cur.execute(
"INSERT OR IGNORE INTO users (tg_user_id, full_name, is_admin) VALUES (?, ?, ?)",
(BOT_ADMIN_ID, "Администратор", 1)
)
        conn.commit()
        conn.close()
    print(f"✅ БД создана. Админ {BOT_ADMIN_ID} добавлен.")

def main():
    print("🚀 Запуск полной установки Telegram-бота...")
    create_files()
    init_database()
    print("\n✅ Установка завершена!")
    print("\n📌 Далее:")
    print("1. Откройте файл .env и вставьте ваш токен бота вместо YOUR_BOT_TOKEN_HERE")
    print("2. Выполните: pip install -r requirements.txt")
    print("3. Запустите: python main.py")

if __name__ == "__main__":
    main()