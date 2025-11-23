from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from database import get_user_by_tg_id
from handlers.user import show_user_menu

common_router = Router()

@common_router.message(F.text == "/start")
@common_router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    user = await get_user_by_tg_id(message.from_user.id)
    if user:
        await show_user_menu(message)
    else:
        await message.answer("👋 Добро пожаловать!\nПожалуйста, введите ваше ФИО:")
        await message.answer("Пример: Иванов Иван Иванович")
        from handlers.user import RegisterStates
        await state.set_state(RegisterStates.waiting_for_name)
def register_common_handlers(dp):
    dp.include_router(common_router)
