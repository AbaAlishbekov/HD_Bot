import logging
import pandas as pd
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Document
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DATA_DICT = {}
ROOT_ID = None

def load_data():
    global DATA_DICT, ROOT_ID
    if not os.path.exists("data.xlsx"):
        DATA_DICT = {}
        ROOT_ID = None
        return
    df = pd.read_excel("data.xlsx")
    DATA_DICT = df.set_index('id').to_dict(orient='index')
    first_row = df.iloc[0]
    ROOT_ID = first_row['id']

def get_children(parent_id):
    children = []
    for item_id, data in DATA_DICT.items():
        if data['parentid'] == parent_id:
            children.append((item_id, data['name']))
    return children

async def show_item(update: Update, context: ContextTypes.DEFAULT_TYPE, item_id: int):
    # Сохраняем текущий id элемента в пользовательских данных
    context.user_data['current_id'] = item_id

    item_data = DATA_DICT.get(item_id)
    if not item_data:
        # Если элемент не найден
        if update.callback_query:
            await update.callback_query.answer("Элемент не найден.", show_alert=True)
        else:
            await update.message.reply_text("Элемент не найден.")
        return

    text_to_send = f"{item_data.get('name', '')}\n\n{item_data.get('text', 'Нет текста')}"
    children = get_children(item_id)

    keyboard = []
    # Кнопки для потомков
    for (child_id, child_name) in children:
        keyboard.append([InlineKeyboardButton(child_name, callback_data=str(child_id))])

    # Кнопка "Назад" - переход к родительскому элементу, если он существует
    parent_id = item_data.get('parentid')
    if parent_id:
        keyboard.append([InlineKeyboardButton("Назад", callback_data="parent")])

    # Кнопка "На главную" - переход к корневому элементу, если текущий не корневой
    if item_id != ROOT_ID:
        keyboard.append([InlineKeyboardButton("На главную", callback_data="root")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=text_to_send,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=text_to_send, 
            reply_markup=reply_markup
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ROOT_ID is None:
        await update.message.reply_text("Нет данных для отображения.")
    else:
        await show_item(update, context, ROOT_ID)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # Обработка кнопки "Назад" - переход к родителю
    if data == "parent":
        current_id = context.user_data.get('current_id')
        if current_id and DATA_DICT.get(current_id, {}).get('parentid'):
            parent_id = DATA_DICT[current_id]['parentid']
            await show_item(update, context, parent_id)
        else:
            await query.answer("Родительский элемент не найден.", show_alert=True)
        return

    # Обработка кнопки "На главную"
    if data == "root":
        if ROOT_ID:
            await show_item(update, context, ROOT_ID)
        else:
            await query.answer("Главный элемент не найден.", show_alert=True)
        return

    # Стандартная обработка выбора пункта
    try:
        item_id = int(data)
    except ValueError:
        await query.answer("Неверные данные.", show_alert=True)
        return

    await show_item(update, context, item_id)

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Используйте: /login <username> <password>")
        return

    username, password = args
    if username == "admin" and password == "ssdsq777":
        context.user_data['is_admin'] = True
        await update.message.reply_text("Вы успешно вошли как администратор.")
    else:
        await update.message.reply_text("Неверные логин или пароль.")

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        await update.message.reply_text("У вас нет прав для этой команды.")
        return

    if not os.path.exists("data.xlsx"):
        await update.message.reply_text("Файл data.xlsx не найден.")
        return

    await update.message.reply_document(document=open("data.xlsx", "rb"))

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        await update.message.reply_text("У вас нет прав для этой команды.")
        return

    await update.message.reply_text("Пришлите новый файл data.xlsx в качестве документа.")

    # Устанавливаем флаг ожидания файла
    context.user_data['awaiting_upload'] = True

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_upload'):
        document: Document = update.message.document
        if document and document.file_name.endswith(".xlsx"):
            file = await document.get_file()
            await file.download_to_drive("data.xlsx")
            # Перезагружаем данные после замены файла
            load_data()
            context.user_data['awaiting_upload'] = False
            await update.message.reply_text("Файл успешно загружен и данные обновлены.")
        else:
            await update.message.reply_text("Пожалуйста, пришлите файл с расширением .xlsx.")
    else:
        await update.message.reply_text("Неожиданный документ.")

def main():
    load_data()
    bot_token = "7731455351:AAEpMobv_3guyekM5Ulx9ETvnj8z2pJ4O40"  # замените на настоящий токен
    application = ApplicationBuilder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("login", login_command))
    application.add_handler(CommandHandler("download", download_command))
    application.add_handler(CommandHandler("upload", upload_command))
    application.add_handler(MessageHandler(filters.Document.FileExtension("xlsx"), handle_document))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
