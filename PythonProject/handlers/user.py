# handlers/user.py
from aiogram import Router, F
from aiogram.types import (
    Message, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_user_by_tg_id, create_user, get_tasks_by_user_id, create_task
import aiosqlite
from pathlib import Path
from datetime import datetime

user_router = Router()
DB_PATH = Path("tasks.db")


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
    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        return

    kb = [[KeyboardButton(text="📋 Мои задачи")]]

    # Добавляем админ-кнопку, если пользователь — админ
    if user["is_admin"]:
        kb.append([KeyboardButton(text="👨‍💼 Админ-панель")])

    await message.answer(
        "✅ Вы зарегистрированы!\nВыберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )


# --- Показ задач с кнопками статуса ---
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
        task_id = task["id"]
        txt = (
            f"📄 <b>Практика:</b> {task['practice_name'] or task['description']}\n"
            f"📅 <b>До:</b> {task['end_date']}\n"
            f"📝 <b>Статус:</b> {task['status']}\n"
            f"💬 <b>Описание:</b> {task['description']}"
        )

        # Формируем кнопки в зависимости от текущего статуса
        buttons = []
        current_status = task["status"]

        if current_status == "ещё не смотрел":
            buttons.append([InlineKeyboardButton(text="🔄 Взять в работу", callback_data=f"status_wip_{task_id}")])
        elif current_status == "в работе":
            buttons.append([InlineKeyboardButton(text="👁️ Просмотрено", callback_data=f"status_reviewed_{task_id}")])
        elif current_status == "просмотренно":
            buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data=f"status_done_{task_id}")])

        # Всегда добавляем кнопку "назад к исходному", если не "ещё не смотрел"
        if current_status != "ещё не смотрел":
            buttons.append(
                [InlineKeyboardButton(text="↩️ Вернуть в исходное", callback_data=f"status_reset_{task_id}")])

        await message.answer(
            txt,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


@user_router.callback_query(F.data.startswith("status_"))
async def handle_status_change(callback: CallbackQuery):
    data = callback.data
    user_tg_id = callback.from_user.id

    # Определяем новый статус и task_id
    if data.startswith("status_wip_"):
        new_status = "в работе"
        task_id = int(data.replace("status_wip_", ""))
    elif data.startswith("status_reviewed_"):
        new_status = "просмотренно"
        task_id = int(data.replace("status_reviewed_", ""))
    elif data.startswith("status_done_"):
        new_status = "готово"
        task_id = int(data.replace("status_done_", ""))
    elif data.startswith("status_reset_"):
        new_status = "ещё не смотрел"
        task_id = int(data.replace("status_reset_", ""))
    else:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    # Обновляем статус и next_reminder в БД
    async with aiosqlite.connect(DB_PATH) as db:
        if new_status == "готово":
            await db.execute(
                "UPDATE tasks SET status = ?, next_reminder = NULL WHERE id = ?",
                (new_status, task_id)
            )
        else:
            await db.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (new_status, task_id)
            )
        await db.commit()

    # Получаем обновлённые данные задачи из БД
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
            task = await cursor.fetchone()

    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    # Получаем практику для отображения
    practice_display = task["practice_name"] or task["description"]

    # Формируем новый текст
    new_text = (
        f"📄 <b>Практика:</b> {practice_display}\n"
        f"📅 <b>До:</b> {task['end_date']}\n"
        f"📝 <b>Статус:</b> {task['status']}\n"
        f"💬 <b>Описание:</b> {task['description']}"
    )

    # Формируем новые кнопки
    buttons = []
    current_status = task["status"]

    if current_status == "ещё не смотрел":
        buttons.append([InlineKeyboardButton(text="🔄 Взять в работу", callback_data=f"status_wip_{task_id}")])
    elif current_status == "в работе":
        buttons.append([InlineKeyboardButton(text="👁️ Просмотрено", callback_data=f"status_reviewed_{task_id}")])
    elif current_status == "просмотренно":
        buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data=f"status_done_{task_id}")])

    if current_status != "ещё не смотрел":
        buttons.append([InlineKeyboardButton(text="↩️ Вернуть в исходное", callback_data=f"status_reset_{task_id}")])

    # Редактируем сообщение
    await callback.message.edit_text(
        new_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer(f"Статус изменён: {new_status}")

# --- Регистрация роутера ---
def register_user_handlers(dp):
    dp.include_router(user_router)