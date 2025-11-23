from aiogram import Dispatcher
from .common import register_common_handlers
from .user import register_user_handlers
from .admin import register_admin_handlers

def register_all_handlers(dp: Dispatcher, bot):
    register_common_handlers(dp)
    register_user_handlers(dp)
    register_admin_handlers(dp)
