import asyncio
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
        print("\n🛑 Бот остановлен.")
