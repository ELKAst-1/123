# handlers/user.py
from aiogram import Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
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
            f"📄 <b>Практика:</b> {task['practice_name'] or task['description']}\n"
            f"📅 <b>До:</b> {task['end_date']}\n"
            f"📝 <b>Статус:</b> {task['status']}\n"
            f"💬 <b>Описание:</b> {task['description']}"
        )
        await message.answer(
            txt,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ готово", callback_data=f"status_done_{task['id']}")],
                [InlineKeyboardButton(text="🔄 в работе", callback_data=f"status_wip_{task['id']}")],
                [InlineKeyboardButton(text="👁️ просмотренно", callback_data=f"status_reviewed_{task['id']}")],
                [InlineKeyboardButton(text="↩️ вернуть", callback_data=f"status_reset_{task['id']}")]
            ])
        )

def register_user_handlers(dp):
    dp.include_router(user_router)
