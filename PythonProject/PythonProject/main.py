import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters
)
from bot.handlers import user, admin
from bot.services.sheets import SheetsService
from bot.services.drive import DriveService
from bot.services.scheduler import SchedulerService
from bot.utils.states import UserStates, AdminStates
from bot.utils.config import TELEGRAM_BOT_TOKEN, ADMIN_USERNAME, GOOGLE_SHEET_ID, GOOGLE_DRIVE_FOLDER_ID

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.bot_data['admin_username'] = ADMIN_USERNAME
    application.bot_data['groups'] = ['ИВТ-21', 'ИВТ-22', 'ИВТ-23', 'ИВТ-24']
    application.bot_data['purposes'] = ['Учебный проект', 'Курсовая работа', 'Диплом', 'Личное использование', 'Другое']
    
    if GOOGLE_SHEET_ID:
        try:
            sheets_service = SheetsService(GOOGLE_SHEET_ID)
            application.bot_data['sheets_service'] = sheets_service
            logger.info("Google Sheets сервис инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Google Sheets: {e}")
    
    if GOOGLE_DRIVE_FOLDER_ID:
        try:
            drive_service = DriveService(GOOGLE_DRIVE_FOLDER_ID)
            application.bot_data['drive_service'] = drive_service
            logger.info("Google Drive сервис инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Google Drive: {e}")
    
    if 'sheets_service' in application.bot_data and 'drive_service' in application.bot_data:
        try:
            scheduler_service = SchedulerService(
                application.bot_data['sheets_service'],
                application.bot_data['drive_service']
            )
            scheduler_service.start()
            application.bot_data['scheduler_service'] = scheduler_service
            logger.info("Планировщик задач запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска планировщика: {e}")
    
    user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('new_request', user.new_request)],
        states={
            UserStates.FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, user.get_first_name)],
            UserStates.LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, user.get_last_name)],
            UserStates.GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, user.get_group)],
            UserStates.PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, user.get_purpose)],
            UserStates.FILE: [MessageHandler(filters.Document.ALL, user.get_file)],
        },
        fallbacks=[CommandHandler('cancel', user.cancel)]
    )
    
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin.admin_menu)],
        states={
            AdminStates.VIEW_REQUESTS: [
                CallbackQueryHandler(admin.view_requests, pattern='^view_requests$'),
                CallbackQueryHandler(admin.manage_groups, pattern='^manage_groups$'),
                CallbackQueryHandler(admin.manage_purposes, pattern='^manage_purposes$'),
                CallbackQueryHandler(admin.accept_request, pattern='^accept_'),
                CallbackQueryHandler(admin.complete_request, pattern='^complete_'),
                CallbackQueryHandler(admin.navigate_pages, pattern='^(next_page|prev_page)$'),
                CallbackQueryHandler(admin.back_to_main_menu, pattern='^main_menu$'),
            ],
            AdminStates.MANAGE_GROUPS: [
                CallbackQueryHandler(admin.add_group_start, pattern='^add_group$'),
                CallbackQueryHandler(admin.remove_group_start, pattern='^remove_group$'),
                CallbackQueryHandler(admin.back_to_main_menu, pattern='^main_menu$'),
            ],
            AdminStates.MANAGE_PURPOSES: [
                CallbackQueryHandler(admin.add_purpose_start, pattern='^add_purpose$'),
                CallbackQueryHandler(admin.remove_purpose_start, pattern='^remove_purpose$'),
                CallbackQueryHandler(admin.back_to_main_menu, pattern='^main_menu$'),
            ],
            AdminStates.ADD_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.add_group_finish)
            ],
            AdminStates.ADD_PURPOSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.add_purpose_finish)
            ],
            AdminStates.REMOVE_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.remove_group_finish)
            ],
            AdminStates.REMOVE_PURPOSE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin.remove_purpose_finish)
            ],
        },
        fallbacks=[CommandHandler('cancel', user.cancel)]
    )
    
    application.add_handler(CommandHandler('start', user.start))
    application.add_handler(user_conv_handler)
    application.add_handler(admin_conv_handler)
    
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
