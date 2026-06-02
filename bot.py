import sqlite3
import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from telebot import TeleBot, types

# 1. Загрузка настроек окружения
load_dotenv()

# Ваша актуальная ссылка ngrok
WEBHOOK_URL = "https://frosting-suffix-corporate.ngrok-free.dev/webhook"
BASE_URL = WEBHOOK_URL.replace('/webhook', '')

TOKEN = os.getenv("TOKEN")
bot = TeleBot(TOKEN)

# Константа с именем нашей базы данных
DB_NAME = "warehouse_bot.db"


# 2. Вспомогательная функция для быстрой проверки роли пользователя в базе
def get_user_role(telegram_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# Функция для автоматической привязки Telegram ID к номеру телефона
def link_telegram_id_by_phone(telegram_id: int, phone: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Очищаем номер от знака +, если Telegram его прислал
    clean_phone = phone.replace("+", "").strip()

    # Проверяем, добавлен ли этот телефон директором
    cursor.execute("SELECT role FROM users WHERE phone = ?", (clean_phone,))
    result = cursor.fetchone()

    if result:
        # Если телефон найден — привязываем к нему текущий Telegram ID
        cursor.execute("UPDATE users SET telegram_id = ? WHERE phone = ?", (telegram_id, clean_phone))
        conn.commit()
        conn.close()
        return result[0]  # Возвращаем чистую строку роли

    conn.close()
    return None


# 4. Менеджер жизненного цикла приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print("🚀 Сервер, база данных и вебхук Telegram успешно настроены через lifespan!")
    yield


# Передаем управление жизненным циклом в FastAPI
app = FastAPI(lifespan=lifespan)


# 5. Эндпоинт для Mini App (выдача вашей HTML страницы формы ввода)
@app.get("/", response_class=HTMLResponse)
async def read_item():
    path_to_html = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(path_to_html):
        with open(path_to_html, "r", encoding="utf-8") as file:
            html_content = file.read()
        return HTMLResponse(content=html_content, status_code=200)
    return HTMLResponse(content="<h3>Файл index.html не найден</h3>", status_code=404)


# 6. Эндпоинт вебхука, который принимает сообщения от Telegram
@app.post("/webhook")
async def telegram_webhook(request: Request):
    if request.headers.get("content-type") == "application/json":
        json_string = await request.json()
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return {"status": "ok"}
    return {"status": "error"}


# =====================================================================
# ОБРАБОТЧИКИ КОМАНД И КНОПОК ТЕЛЕГРАМ-БОТА
# =====================================================================

# Главное меню, которое перестраивается в зависимости от роли
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id

    # Сначала жестко чистим старый кэш кнопок
    bot.send_message(message.chat.id, "Синхронизация интерфейса...", reply_markup=types.ReplyKeyboardRemove())

    # Проверяем роль в нашей базе данных
    role = get_user_role(user_id)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    web_send = types.WebAppInfo(url=f"{BASE_URL}/")

    # 1. Кнопка отправки доступна всем авторизованным пользователям
    btn_send = types.KeyboardButton("📤 Отправить инвентарь", web_app=web_send)
    markup.add(btn_send)

    # 2. ЕСЛИ ЭТО АДМИНИСТРАТОР — добавляем уникальную кнопку Сканирования инфо
    if role == "Администратор":
        # Передаем специальный параметр ?mode=inspect, чтобы HTML понял задачу
        web_inspect = types.WebAppInfo(url=f"{BASE_URL}/?mode=inspect")
        btn_inspect = types.KeyboardButton("🔍 Инфо по штрихкоду", web_app=web_inspect)
        markup.add(btn_inspect)

    # 3. Закрепляем кнопку «Офис» слева от ввода текста
    web_office = types.WebAppInfo(url=f"{BASE_URL}/")
    bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=types.MenuButtonWebApp(type="web_app", text="🏢 Офис", web_app=web_office)
    )

    welcome_text = f"🤖 Бот STS готов к работе.\nВаша роль в системе: *{role if role else 'Не авторизован'}*.\n\n"
    if role == "Администратор":
        welcome_text += "👑 Вам, как Администратору, доступна скрытая кнопка «🔍 Инфо по штрихкоду» для полной проверки истории устройств."
    else:
        welcome_text += "Используйте нижнюю кнопку для отправки оборудования на объекты."

    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")


# Запасной текстовый обработчик
@bot.message_handler(func=lambda message: True)
def handle_text_fallback(message):
    if message.text == "🏢 Офис" or message.text == "/office":
        role = get_user_role(message.from_user.id)
        if not role:
            bot.reply_to(message, "❌ Вас нет в списке сотрудников. Пройдите верификацию по номеру телефона.")
        else:
            bot.reply_to(message, f"Ваша роль: {role}. Используйте кнопку приложения «Офис» у поля ввода.")


# =====================================================================
# ПРИЕМ ДАННЫХ ИЗ ФОРМЫ (ОТПРАВКА ИЛИ ИНСПЕКЦИЯ ШТРИХКОДА)
# =====================================================================

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        # 1. ОБРАБОТКА РЕГИСТРАЦИИ ПОЛЬЗОВАТЕЛЯ
        if action == "register":
            name = data.get("name")
            role = data.get("role")
            if register_new_user(message.from_user.id, name, role):
                bot.send_message(message.chat.id,
                                 f"🎉 **Регистрация успешна!**\n\nСотрудник: *{name}*\nРоль: *{role}*\nВведите команду `/start` для обновления меню кнопок.")
            return

        # 2. ОБРАБОТКА ОБЫЧНОЙ ОТПРАВКИ ИНВЕНТАРЯ
        elif action == "send_inventory":
            barcode = data.get("barcode")
            name = data.get("name")
            destination = data.get("destination")
            status = data.get("status")
            desc = data.get("description", "")

            # В реальном коде здесь будет запись INSERT INTO logistics и inventory
            msg_to_sender = (
                f"📤 **Вы отправили инвентарь!**\n\n"
                f"📦 Устройство: *{name}*\n"
                f"🔢 Штрихкод: `{barcode}`\n"
                f"📍 Направление: *{destination}*\n"
                f"⚙️ Состояние: *{status}*\n"
            )
            if desc: msg_to_sender += f"⚠️ Поломка: _{desc}_\n"
            msg_to_sender += "\n⏳ *Ожидание подтверждения адресатом...*"
            bot.send_message(message.chat.id, msg_to_sender, parse_mode="Markdown")

            # Тестовая имитация зависающего сообщения получателя
            inline_markup = types.InlineKeyboardMarkup()
            inline_markup.add(types.InlineKeyboardButton("✅ Подтвердить получение", callback_data=f"confirm_{barcode}"))

            msg_to_receiver = f"📥 **Вам отправлено оборудование!**\n\n📦 Устройство: *{name}*\n🔢 Штрихкод: `{barcode}`\n\nПожалуйста, подтвердите приемку:"
            bot.send_message(message.chat.id, msg_to_receiver, reply_markup=inline_markup, parse_mode="Markdown")

        # 3. НОВАЯ ЛОГИКА: АДМИН-ОТЧЕТ ПО ШТРИХКОДУ
        elif action == "inspect_barcode":
            barcode = data.get("barcode")

            # Делаем запросы в базу данных SQLite
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            # Получаем текущий статус из таблицы inventory
            cursor.execute("SELECT name, current_location, status, issue_description FROM inventory WHERE barcode = ?",
                           (barcode,))
            inv_data = cursor.fetchone()
            conn.close()

            if not inv_data:
                bot.send_message(message.chat.id,
                                 f"🔍 **Инспекция штрихкода:** `{barcode}`\n\n❌ Данное устройство еще ни разу не вносилось в общую базу данных.")
                return

            name, location, status, issue = inv_data

            # Формируем красивую карточку истории устройства
            report = (
                f"📋 **ДОСЬЕ ОБОРУДОВАНИЯ (Админ)**\n\n"
                f"📦 Название: *{name}*\n"
                f"🔢 Штрихкод: `{barcode}`\n"
                f"📍 Где сейчас: *{location}*\n"
                f"⚙️ Текущий статус: *{status}*\n"
            )
            if issue:
                report += f"❌ Описание поломки: _{issue}_\n"

            # Имитируем логи истории перемещений (в будущем запросом из таблицы logistics)
            report += (
                f"\n⏳ **История перемещений:**\n"
                f"• _24.05.2026_ — Перемещено: Склад ➔ АЗС №3 (Куратор Иванов)\n"
                f"• _01.06.2026_ — Выявлена неисправность: {issue if issue else 'Нет'}\n"
            )

            # Если устройство неисправно, добавляем Админу инлайн-кнопку ремонта прямо в чат!
            inline_markup = types.InlineKeyboardMarkup()
            if status == "Неисправен":
                btn_repair = types.InlineKeyboardButton("🔧 Отметить как ОТРЕМОНТИРОВАНО",
                                                        callback_data=f"repair_{barcode}")
                inline_markup.add(btn_repair)
                report += "\n🛠 Вы можете закрыть заявку на ремонт кнопкой ниже:"

            bot.send_message(message.chat.id, report, reply_markup=inline_markup, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка обработки: {e}")


# 4. ОБРАБОТЧИКИ НАЖАТИЙ НА ИНЛАЙН-КНОПКИ В СЛУЖЕБНЫХ ПОСТАХ
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Кнопка подтверждения приемки логгера
    if call.data.startswith("confirm_"):
        barcode = call.data.split("_")[1]
        try:
            bot.delete_message(chat_id, message_id)  # Удаляем зависший пост
            bot.send_message(chat_id,
                             f"✅ **Перемещение завершено!**\nУстройство `{barcode}` успешно принято на объекте.")
        except Exception as e:
            print(e)

    # НОВАЯ КНОПКА: Смена статуса на "Отремонтировано"
    elif call.data.startswith("repair_"):
        barcode = call.data.split("_")[1]
        try:
            # Обновляем статус железки прямо в базе данных SQLite
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET status = 'Работает', issue_description = NULL WHERE barcode = ?",
                           (barcode,))
            conn.commit()
            conn.close()

            # Редактируем текущий текст сообщения админа, убирая кнопку ремонта
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ **Статус изменен на «Работает»**\n\nУстройство со штрихкодом `{barcode}` успешно отремонтировано и готово к повторной отправке на объекты компании STS!",
                reply_markup=None  # Кнопка исчезает
            )
        except Exception as e:
            bot.send_message(chat_id, f"❌ Ошибка при обновлении статуса ремонта: {e}")


# Перехватчик номера телефона контактов (остается прежним)
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    role = link_telegram_id_by_phone(user_id, phone)
    if role:
        bot.send_message(message.chat.id, f"✅ Успешно! Ваша роль: *{role}*. Наберите `/start` для активации кнопок.",
                         parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, f"❌ Номер `{phone}` не найден.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("bot:app", host="127.0.0.1", port=8000, reload=True)
