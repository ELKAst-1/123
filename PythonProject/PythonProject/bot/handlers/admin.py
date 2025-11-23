from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot.utils.states import AdminStates

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_username = context.bot_data.get('admin_username')
    
    if user.username != admin_username:
        await update.message.reply_text("У вас нет прав администратора.")
        return ConversationHandler.END
    
    context.bot_data['admin_user_id'] = user.id
    
    keyboard = [
        [InlineKeyboardButton("📋 Просмотр заявок", callback_data='view_requests')],
        [InlineKeyboardButton("📝 Управление группами", callback_data='manage_groups')],
        [InlineKeyboardButton("🎯 Управление целями печати", callback_data='manage_purposes')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Панель администратора:",
        reply_markup=reply_markup
    )
    
    return AdminStates.VIEW_REQUESTS

async def view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sheets_service = context.bot_data.get('sheets_service')
    
    if not sheets_service:
        await query.edit_message_text("Ошибка: сервис не инициализирован.")
        return ConversationHandler.END
    
    try:
        requests = sheets_service.get_all_requests()
        
        if not requests:
            await query.edit_message_text("Заявок пока нет.")
            return ConversationHandler.END
        
        page = context.user_data.get('page', 0)
        items_per_page = 5
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_requests = requests[start_idx:end_idx]
        
        text = "📋 Список заявок:\n\n"
        
        for req in page_requests:
            status_emoji = {
                'В очереди': '⚪',
                'В работе': '🟡',
                'Готово': '🔴'
            }.get(req.get('Статус', ''), '⚪')
            
            text += (
                f"{status_emoji} ID: {req.get('ID')}\n"
                f"Имя: {req.get('Имя')} {req.get('Фамилия')}\n"
                f"Группа: {req.get('Группа')}\n"
                f"Цель: {req.get('Цель печати')}\n"
                f"Статус: {req.get('Статус')}\n"
                f"Дата: {req.get('Дата')}\n"
                f"───────────────\n"
            )
        
        keyboard = []
        
        for req in page_requests:
            if req.get('Статус') == 'В очереди':
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Принять в работу #{req.get('ID')[:4]}",
                        callback_data=f"accept_{req.get('ID')}"
                    )
                ])
            elif req.get('Статус') == 'В работе':
                keyboard.append([
                    InlineKeyboardButton(
                        f"✔️ Готово #{req.get('ID')[:4]}",
                        callback_data=f"complete_{req.get('ID')}"
                    )
                ])
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data='prev_page'))
        if end_idx < len(requests):
            nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data='next_page'))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        print(f"Ошибка при просмотре заявок: {e}")
        await query.edit_message_text(f"Произошла ошибка: {e}")
    
    return AdminStates.VIEW_REQUESTS

async def accept_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    request_id = query.data.split('_')[1]
    sheets_service = context.bot_data.get('sheets_service')
    
    try:
        sheets_service.update_status(request_id, 'В работе')
        
        request_data = sheets_service.get_request_by_id(request_id)
        if request_data and request_data.get('Telegram ID'):
            try:
                await context.bot.send_message(
                    chat_id=int(request_data['Telegram ID']),
                    text=f"📢 Ваша заявка #{request_id} принята в работу!"
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление пользователю: {e}")
        
        await query.answer("Заявка принята в работу!")
        await view_requests(update, context)
        
    except Exception as e:
        print(f"Ошибка при принятии заявки: {e}")
        await query.answer(f"Ошибка: {e}")

async def complete_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    request_id = query.data.split('_')[1]
    sheets_service = context.bot_data.get('sheets_service')
    
    try:
        sheets_service.update_status(request_id, 'Готово')
        
        request_data = sheets_service.get_request_by_id(request_id)
        if request_data and request_data.get('Telegram ID'):
            try:
                await context.bot.send_message(
                    chat_id=int(request_data['Telegram ID']),
                    text=f"✅ Ваша заявка #{request_id} готова! Можете забрать изделие."
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление пользователю: {e}")
        
        await query.answer("Заявка помечена как готовая!")
        await view_requests(update, context)
        
    except Exception as e:
        print(f"Ошибка при завершении заявки: {e}")
        await query.answer(f"Ошибка: {e}")

async def navigate_pages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'next_page':
        context.user_data['page'] = context.user_data.get('page', 0) + 1
    elif query.data == 'prev_page':
        context.user_data['page'] = max(0, context.user_data.get('page', 0) - 1)
    
    await view_requests(update, context)

async def manage_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    groups = context.bot_data.get('groups', [])
    
    text = "📝 Управление группами:\n\n"
    text += "Текущие группы:\n"
    
    if groups:
        for idx, group in enumerate(groups, 1):
            text += f"{idx}. {group}\n"
    else:
        text += "Список пуст\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить группу", callback_data='add_group')],
        [InlineKeyboardButton("➖ Удалить группу", callback_data='remove_group')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return AdminStates.MANAGE_GROUPS

async def manage_purposes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    purposes = context.bot_data.get('purposes', [])
    
    text = "🎯 Управление целями печати:\n\n"
    text += "Текущие цели:\n"
    
    if purposes:
        for idx, purpose in enumerate(purposes, 1):
            text += f"{idx}. {purpose}\n"
    else:
        text += "Список пуст\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить цель", callback_data='add_purpose')],
        [InlineKeyboardButton("➖ Удалить цель", callback_data='remove_purpose')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return AdminStates.MANAGE_PURPOSES

async def add_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("Введите название новой группы:")
    
    return AdminStates.ADD_GROUP

async def add_group_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_group = update.message.text.strip()
    
    groups = context.bot_data.get('groups', [])
    
    if new_group not in groups:
        groups.append(new_group)
        context.bot_data['groups'] = groups
        message_text = f"✅ Группа '{new_group}' добавлена!\n\n"
    else:
        message_text = f"❌ Группа '{new_group}' уже существует.\n\n"
    
    text = message_text + "📝 Управление группами:\n\nТекущие группы:\n"
    
    if groups:
        for idx, group in enumerate(groups, 1):
            text += f"{idx}. {group}\n"
    else:
        text += "Список пуст\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить группу", callback_data='add_group')],
        [InlineKeyboardButton("➖ Удалить группу", callback_data='remove_group')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    
    return AdminStates.MANAGE_GROUPS

async def add_purpose_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("Введите название новой цели печати:")
    
    return AdminStates.ADD_PURPOSE

async def add_purpose_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_purpose = update.message.text.strip()
    
    purposes = context.bot_data.get('purposes', [])
    
    if new_purpose not in purposes:
        purposes.append(new_purpose)
        context.bot_data['purposes'] = purposes
        message_text = f"✅ Цель '{new_purpose}' добавлена!\n\n"
    else:
        message_text = f"❌ Цель '{new_purpose}' уже существует.\n\n"
    
    text = message_text + "🎯 Управление целями печати:\n\nТекущие цели:\n"
    
    if purposes:
        for idx, purpose in enumerate(purposes, 1):
            text += f"{idx}. {purpose}\n"
    else:
        text += "Список пуст\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить цель", callback_data='add_purpose')],
        [InlineKeyboardButton("➖ Удалить цель", callback_data='remove_purpose')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    
    return AdminStates.MANAGE_PURPOSES

async def remove_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    groups = context.bot_data.get('groups', [])
    
    if not groups:
        await query.edit_message_text("Список групп пуст. Нечего удалять.")
        return AdminStates.MANAGE_GROUPS
    
    text = "Выберите группу для удаления:\n\n"
    for idx, group in enumerate(groups, 1):
        text += f"{idx}. {group}\n"
    text += "\nВведите номер группы:"
    
    await query.edit_message_text(text)
    return AdminStates.REMOVE_GROUP

async def remove_group_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        group_num = int(update.message.text.strip())
        groups = context.bot_data.get('groups', [])
        
        if 1 <= group_num <= len(groups):
            removed_group = groups.pop(group_num - 1)
            context.bot_data['groups'] = groups
            message_text = f"✅ Группа '{removed_group}' удалена!\n\n"
        else:
            message_text = "❌ Неверный номер группы.\n\n"
    except ValueError:
        message_text = "❌ Пожалуйста, введите число.\n\n"
    
    groups = context.bot_data.get('groups', [])
    text = message_text + "📝 Управление группами:\n\nТекущие группы:\n"
    
    if groups:
        for idx, group in enumerate(groups, 1):
            text += f"{idx}. {group}\n"
    else:
        text += "Список пуст\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить группу", callback_data='add_group')],
        [InlineKeyboardButton("➖ Удалить группу", callback_data='remove_group')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    
    return AdminStates.MANAGE_GROUPS

async def remove_purpose_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    purposes = context.bot_data.get('purposes', [])
    
    if not purposes:
        await query.edit_message_text("Список целей пуст. Нечего удалять.")
        return AdminStates.MANAGE_PURPOSES
    
    text = "Выберите цель для удаления:\n\n"
    for idx, purpose in enumerate(purposes, 1):
        text += f"{idx}. {purpose}\n"
    text += "\nВведите номер цели:"
    
    await query.edit_message_text(text)
    return AdminStates.REMOVE_PURPOSE

async def remove_purpose_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        purpose_num = int(update.message.text.strip())
        purposes = context.bot_data.get('purposes', [])
        
        if 1 <= purpose_num <= len(purposes):
            removed_purpose = purposes.pop(purpose_num - 1)
            context.bot_data['purposes'] = purposes
            message_text = f"✅ Цель '{removed_purpose}' удалена!\n\n"
        else:
            message_text = "❌ Неверный номер цели.\n\n"
    except ValueError:
        message_text = "❌ Пожалуйста, введите число.\n\n"
    
    purposes = context.bot_data.get('purposes', [])
    text = message_text + "🎯 Управление целями печати:\n\nТекущие цели:\n"
    
    if purposes:
        for idx, purpose in enumerate(purposes, 1):
            text += f"{idx}. {purpose}\n"
    else:
        text += "Список пуст\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить цель", callback_data='add_purpose')],
        [InlineKeyboardButton("➖ Удалить цель", callback_data='remove_purpose')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    
    return AdminStates.MANAGE_PURPOSES

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📋 Просмотр заявок", callback_data='view_requests')],
        [InlineKeyboardButton("📝 Управление группами", callback_data='manage_groups')],
        [InlineKeyboardButton("🎯 Управление целями печати", callback_data='manage_purposes')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Панель администратора:",
        reply_markup=reply_markup
    )
    
    return AdminStates.VIEW_REQUESTS
