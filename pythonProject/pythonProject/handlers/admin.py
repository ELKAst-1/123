# handlers/admin.py
from aiogram import Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import (
    get_user_by_full_name, set_user_admin, wipe_tasks, wipe_users_except_admin,
    get_all_tasks_for_export, get_or_create_user_by_full_name, add_tasks_from_excel, create_task,
    get_user_tasks_by_full_name, update_task_reminder
)
from utils.excel import export_tasks_to_excel, parse_excel, create_excel_template, normalize_date
import tempfile
import os
from datetime import datetime, timedelta

admin_router = Router()

async def is_admin(tg_id: int) -> bool:
    from database import get_user_by_tg_id
    user = await get_user_by_tg_id(tg_id)
    return bool(user and user["is_admin"])

class AddTaskManually(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_practice_name = State()
    waiting_for_end_date = State()

class AdminManageStates(StatesGroup):
    waiting_name = State()
    waiting_confirm = State()

class WipeStates(StatesGroup):
    confirm_tasks = State()
    confirm_users = State()

class SetReminderStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_task_choice = State()
    waiting_for_reminder_choice = State()
    waiting_for_custom_datetime = State()

# === Основная панель ===

@admin_router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return
    kb = [
        [KeyboardButton(text="📥 Выгрузить все задачи")],
        [KeyboardButton(text="📤 Загрузить Excel")],
        [KeyboardButton(text="➕ Добавить задачу вручную")],
        [KeyboardButton(text="⏰ Настроить напоминание")],
        [KeyboardButton(text="👑 Назначить/удалить админа")],
        [KeyboardButton(text="🧹 Очистить БД")]
    ]
    await message.answer(
        "👨‍💼 Панель администратора\n\n"
        "• 📥 Выгрузить все задачи\n"
        "• 📤 Загрузить Excel\n"
        "• ➕ Добавить задачу вручную\n"
        "• ⏰ Настроить напоминание\n"
        "• 👑 Назначить/удалить админа\n"
        "• 🧹 Очистить БД",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    )

# === Настройка напоминания ===

@admin_router.message(F.text == "⏰ Настроить напоминание")
async def start_set_reminder(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("⏰ Введите ФИО преподавателя:")
    await state.set_state(SetReminderStates.waiting_for_full_name)

@admin_router.message(SetReminderStates.waiting_for_full_name)
async def process_reminder_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    tasks = await get_user_tasks_by_full_name(full_name)
    if not tasks:
        await message.answer("❌ У преподавателя нет задач.")
        await state.clear()
        return
    await state.update_data(full_name=full_name, tasks=tasks)
    task_list = "\n".join([
        f"{i+1}. {(t['practice_name'] or t['description'])[:30]}... (до {t['end_date']})"
        for i, t in enumerate(tasks)
    ])
    await message.answer(f"📋 Выберите задачу (1–{len(tasks)}):\n{task_list}")
    await state.set_state(SetReminderStates.waiting_for_task_choice)

@admin_router.message(SetReminderStates.waiting_for_task_choice)
async def process_task_choice(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip()) - 1
        data = await state.get_data()
        task = data["tasks"][idx]
        await state.update_data(selected_task_id=task["id"])
        await message.answer(
            "🕒 Выберите напоминание:\n"
            "• 1 — через 1 день\n"
            "• 3 — через 3 дня\n"
            "• 7 — через неделю\n"
            "• Или введите дату: 2025-07-20 14:30"
        )
        await state.set_state(SetReminderStates.waiting_for_reminder_choice)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный номер. Попробуйте снова.")

@admin_router.message(SetReminderStates.waiting_for_reminder_choice)
async def process_reminder_choice(message: Message, state: FSMContext):
    text = message.text.strip()
    from datetime import datetime, timedelta
    try:
        if text in ("1", "3", "7"):
            days = int(text)
            dt = datetime.now() + timedelta(days=days)
            reminder_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            reminder_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        data = await state.get_data()
        await update_task_reminder(data["selected_task_id"], reminder_str)
        await message.answer(f"✅ Напоминание установлено на {reminder_str}")
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте 1/3/7 или ДД.ММ.ГГГГ ЧЧ:ММ")

# === Остальные хендлеры (без изменений) ===

@admin_router.message(F.text == "➕ Добавить задачу вручную")
async def start_add_task(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🆕 Введите ФИО преподавателя:")
    await state.set_state(AddTaskManually.waiting_for_full_name)

@admin_router.message(AddTaskManually.waiting_for_full_name)
async def process_full_name_step(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("❌ Введите полное ФИО (минимум имя и фамилия).")
        return
    await state.update_data(full_name=full_name)
    await message.answer("Введите название практики или описание задачи:")
    await state.set_state(AddTaskManually.waiting_for_practice_name)

@admin_router.message(AddTaskManually.waiting_for_practice_name)
async def process_practice_name_step(message: Message, state: FSMContext):
    practice_name = message.text.strip()
    await state.update_data(practice_name=practice_name)
    await message.answer("Укажите дату окончания (15.07.2025 или 2025-07-15):")
    await state.set_state(AddTaskManually.waiting_for_end_date)

@admin_router.message(AddTaskManually.waiting_for_end_date)
async def process_end_date_step(message: Message, state: FSMContext):
    end_date = normalize_date(message.text.strip())
    if not end_date:
        await message.answer("❌ Неверный формат даты.")
        return
    data = await state.get_data()
    user_id = await get_or_create_user_by_full_name(data["full_name"])
    if not user_id:
        await message.answer("❌ Не удалось создать пользователя.")
        await state.clear()
        return
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    next_reminder = (end_dt - timedelta(days=7)).strftime("%Y-%m-%d 09:00:00")
    await create_task(
        practice_name=data["practice_name"],
        end_date=end_date,
        user_id=user_id,
        description=data["practice_name"],
        status="ещё не смотрел",
        next_reminder=next_reminder
    )
    await message.answer(f"✅ Задача добавлена для {data['full_name']}")
    await state.clear()

# ... остальные хендлеры (загрузка Excel, выгрузка, управление админами, очистка) — без изменений
from utils.excel import (
    export_tasks_to_excel,
    parse_excel_from_bytes,  # ← добавлено вместо parse_excel
    create_excel_template,
    normalize_date
)
@admin_router.message(F.text == "📤 Загрузить Excel")
async def request_excel_upload(message: Message):
    if not await is_admin(message.from_user.id):
        return
    template_path = create_excel_template()
    await message.answer_document(FSInputFile(template_path, filename="шаблон.xlsx"))
    os.unlink(template_path)

@admin_router.message(F.document)
async def handle_excel_upload(message: Message):
    if not await is_admin(message.from_user.id):
        return

    if not message.document.file_name.endswith('.xlsx'):
        await message.answer("❌ Поддерживаются только .xlsx файлы.")
        return

    try:
        # Скачиваем файл в память
        file = await message.bot.download(message.document.file_id)
        from io import BytesIO
        file_bytes = BytesIO(file.read())

        # Парсим прямо из памяти
        tasks = parse_excel_from_bytes(file_bytes)
        if not tasks:
            await message.answer("❌ Файл не содержит валидных задач.")
            return

        added = await add_tasks_from_excel(tasks)
        await message.answer(f"✅ Добавлено новых задач: {added}")

    except ValueError as e:
        await message.answer(f"❌ Ошибка формата: {e}")
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки: {str(e)}")

@admin_router.message(F.text == "📥 Выгрузить все задачи")
async def export_all_tasks(message: Message):
    if not await is_admin(message.from_user.id):
        return
    tasks = await get_all_tasks_for_export()
    if not tasks:
        await message.answer("📭 Нет задач.")
        return
    filepath = export_tasks_to_excel(tasks)
    await message.answer_document(FSInputFile(filepath))
    os.remove(filepath)

# ... (остальные хендлеры — как у вас, без изменений)

def register_admin_handlers(dp):
    dp.include_router(admin_router)