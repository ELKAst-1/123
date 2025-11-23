from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from bot.utils.states import UserStates
from bot.utils.config import GROUPS, PRINT_PURPOSES
import os
import uuid

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.username == context.bot_data.get('admin_username'):
        await update.message.reply_text(
            f"Привет, {user.first_name}!\n\n"
            f"Вы вошли как администратор.\n"
            f"Используйте /admin для управления заявками."
        )
    else:
        await update.message.reply_text(
            f"Привет, {user.first_name}!\n\n"
            f"Я помогу вам создать заявку на 3D-печать.\n"
            f"Используйте /new_request для создания новой заявки."
        )
    
    return ConversationHandler.END

async def new_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Давайте создадим заявку на 3D-печать.\n\n"
        "Введите ваше имя:"
    )
    return UserStates.FIRST_NAME

async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['first_name'] = update.message.text
    await update.message.reply_text("Введите вашу фамилию:")
    return UserStates.LAST_NAME

async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['last_name'] = update.message.text
    
    groups = context.bot_data.get('groups', [])
    
    if not groups:
        await update.message.reply_text(
            "Список групп пуст. Обратитесь к администратору."
        )
        return ConversationHandler.END
    
    keyboard = [[group] for group in groups]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "Выберите вашу группу:",
        reply_markup=reply_markup
    )
    return UserStates.GROUP

async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['group'] = update.message.text
    
    purposes = context.bot_data.get('purposes', [])
    
    if not purposes:
        await update.message.reply_text(
            "Список целей печати пуст. Обратитесь к администратору."
        )
        return ConversationHandler.END
    
    keyboard = [[purpose] for purpose in purposes]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "Выберите цель печати:",
        reply_markup=reply_markup
    )
    return UserStates.PURPOSE

async def get_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['purpose'] = update.message.text
    
    await update.message.reply_text(
        "Отлично! Теперь прикрепите .stl файл для печати:",
        reply_markup=ReplyKeyboardRemove()
    )
    return UserStates.FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    if not document or not document.file_name.endswith('.stl'):
        await update.message.reply_text(
            "Пожалуйста, прикрепите файл с расширением .stl"
        )
        return UserStates.FILE
    
    file = await context.bot.get_file(document.file_id)
    
    os.makedirs('temp_files', exist_ok=True)
    file_path = f"temp_files/{document.file_name}"
    await file.download_to_drive(file_path)
    
    context.user_data['file_path'] = file_path
    context.user_data['file_name'] = document.file_name
    
    sheets_service = context.bot_data.get('sheets_service')
    drive_service = context.bot_data.get('drive_service')
    
    if not sheets_service or not drive_service:
        await update.message.reply_text(
            "Ошибка: сервисы не инициализированы. Обратитесь к администратору."
        )
        return ConversationHandler.END
    
    try:
        request_id = str(uuid.uuid4())[:8]
        
        file_url, file_id = drive_service.upload_file(file_path, f"{request_id}_{document.file_name}")
        
        request_data = {
            'id': request_id,
            'first_name': context.user_data['first_name'],
            'last_name': context.user_data['last_name'],
            'group': context.user_data['group'],
            'purpose': context.user_data['purpose'],
            'file_url': file_url,
            'file_id': file_id,
            'telegram_id': update.effective_user.id,
            'username': update.effective_user.username or ''
        }
        
        sheets_service.add_request(request_data)
        
        os.remove(file_path)
        
        pending_count = sheets_service.get_pending_count()
        queue_position = pending_count - 1
        
        await update.message.reply_text(
            f"✅ Заявка принята!\n\n"
            f"ID заявки: {request_id}\n"
            f"Перед вами в очереди: {queue_position} человек(а)\n\n"
            f"Вы получите уведомление при изменении статуса."
        )
        
        admin_username = context.bot_data.get('admin_username')
        if admin_username:
            admin_user_id = context.bot_data.get('admin_user_id')
            if admin_user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_user_id,
                        text=f"📬 Новая заявка #{request_id}\n"
                             f"От: {request_data['first_name']} {request_data['last_name']}\n"
                             f"Группа: {request_data['group']}\n"
                             f"Цель: {request_data['purpose']}\n"
                             f"Файл: {file_url}"
                    )
                except Exception as e:
                    print(f"Не удалось отправить уведомление админу: {e}")
        
    except Exception as e:
        print(f"Ошибка при обработке заявки: {e}")
        await update.message.reply_text(
            f"Произошла ошибка при обработке заявки. Попробуйте позже."
        )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Создание заявки отменено.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END
