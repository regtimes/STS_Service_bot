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

# Вставьте сюда вашу АКТУАЛЬНУЮ ссылку из консоли ngrok
WEBHOOK_URL = "https://frosting-suffix-corporate.ngrok-free.dev/webhook"
BASE_URL = WEBHOOK_URL.replace('/webhook', '')

TOKEN = os.getenv("TOKEN")
bot = TeleBot(TOKEN)
DB_NAME = "warehouse_bot.db"


# Проверка роли пользователя в БД
def get_user_role(telegram_id: int):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Ошибка БД: {e}")
        return None


# Регистрация нового сотрудника через "Офис"
def register_new_user(telegram_id: int, name: str, role: str):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT
                       OR IGNORE INTO users (telegram_id, name, role, region_id)
            VALUES (?, ?, ?, 'Не указан')
                       """, (telegram_id, name, role))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка регистрации: {e}")
        return False


# 2. Жизненный цикл FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print("🚀 Сервер запущен по правильной логике! Вебхук привязан.")
    yield


app = FastAPI(lifespan=lifespan)


# 3. Выдача HTML-страницы для Кабинета "Офис" и Форм
@app.get("/", response_class=HTMLResponse)
async def read_html():
    path_to_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if not os.path.exists(path_to_html):
        path_to_html = os.path.join(os.getcwd(), "index.html")

    if os.path.exists(path_to_html):
        with open(path_to_html, "r", encoding="utf-8") as file:
            return HTMLResponse(content=file.read(), status_code=200)
    return HTMLResponse(content="<h3>Файл index.html не найден</h3>", status_code=404)


# 4. Прием вебхуков от Telegram
@app.post("/webhook")
async def telegram_webhook(request: Request):
    if request.headers.get("content-type") == "application/json":
        json_string = await request.json()
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return {"status": "ok"}
    return {"status": "error"}


# =====================================================================
# ОБРАБОТЧИКИ ТЕЛЕГРАМ-БОТА (ТЕКСТ И КНОПКИ)
# =====================================================================

@bot.message_handler(commands=['start'])
def start_cmd(message):
    # Принудительно чистим старый кэш
    bot.send_message(message.chat.id, "Обновление конфигурации кнопок...", reply_markup=types.ReplyKeyboardRemove())

    # 1. Нижнее меню — ОБЫЧНЫЕ ТЕКСТОВЫЕ КНОПКИ (как было в начале)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_send = types.KeyboardButton("📤 Отправить")
    btn_receive = types.KeyboardButton("📥 Получить")
    markup.add(btn_send, btn_receive)

    # 2. Меню "Офис" СЛЕВА от поля ввода (Открывает личный кабинет)
    web_office = types.WebAppInfo(url=f"{BASE_URL}/")
    bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=types.MenuButtonWebApp(type="web_app", text="🏢 Офис", web_app=web_office)
    )

    bot.send_message(
        message.chat.id,
        "🤖 Бот STS готов к работе.\n\n"
        "• Нажимайте кнопки внизу чата для логистики.\n"
        "• Кнопка «Офис» слева внизу откроет личный кабинет или форму регистрации.",
        reply_markup=markup
    )


# Логика обработки нажатий обычных нижних кнопок чата
@bot.message_handler(func=lambda message: True)
def handle_text_buttons(message):
    if message.text == "📤 Отправить":
        # Создаем кнопку вызова сканера камеры ПРЯМО в сообщении чата
        inline_markup = types.InlineKeyboardMarkup()
        web_scan = types.WebAppInfo(url=f"{BASE_URL}/")  # Откроет HTML, где сработает камера
        inline_markup.add(types.InlineKeyboardButton("📷 Открыть камеру-сканер", web_app=web_scan))

        bot.send_message(
            message.chat.id,
            "Для оформления отправки нажмите на кнопку ниже и отсканируйте штрихкод устройства:",
            reply_markup=inline_markup
        )

    elif message.text == "📥 Получить":
        inline_markup = types.InlineKeyboardMarkup()
        web_scan = types.WebAppInfo(url=f"{BASE_URL}/")
        inline_markup.add(types.InlineKeyboardButton("📷 Сканировать код при приемке", web_app=web_scan))

        bot.send_message(
            message.chat.id,
            "Для подтверждения получения нажмите на кнопку ниже:",
            reply_markup=inline_markup
        )


# 5. ПРИЕМ ДАННЫХ ИЗ HTML (Регистрация или Данные формы перемещения)
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        # ЕСЛИ ЭТО РЕГИСТРАЦИЯ ИЗ КАБИНЕТА ОФИС
        if action == "register":
            user_name = data.get("name")
            user_role = data.get("role")

            success = register_new_user(message.from_user.id, user_name, user_role)
            if success:
                bot.send_message(
                    message.chat.id,
                    f"🎉 **Регистрация успешна!**\n\nСотрудник: *{user_name}*\nВыбранная роль: *{user_role}*\nТеперь при открытии «Офиса» вам будет доступно рабочее меню вашей роли.",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(message.chat.id, "❌ Ошибка при сохранении данных регистрации.")

        # ЕСЛИ ЭТО ОТПРАВКА ИНВЕНТАРЯ ИЗ КАМЕРЫ-ФОРМЫ
        elif action == "send":
            barcode = data.get("barcode")
            name = data.get("name")
            destination = data.get("destination")
            status = data.get("status")
            desc = data.get("description", "")

            msg_text = (
                f"🚨 **Оформлена отправка инвентаря!**\n\n"
                f"📦 Устройство: *{name}*\n"
                f"🔢 Штрихкод: `{barcode}`\n"
                f"📍 Направление: *{destination}*\n"
                f"⚙️ Состояние: *{status}*\n"
            )
            if desc: msg_text += f"⚠️ Поломка: _{desc}_\n"
            msg_text += "\n⏳ *Ожидание подтверждения адресатом...*"

            bot.send_message(message.chat.id, msg_text, parse_mode="Markdown")

        # ЕСЛИ ЭТО ПРИЕМКА ИНВЕНТАРЯ
        elif action == "receive":
            barcode = data.get("barcode")
            bot.send_message(
                message.chat.id,
                f"✅ **Успешная приемка!**\n\nУстройство со штрихкодом `{barcode}` успешно получено сотрудником. База данных обновлена.",
                parse_mode="Markdown"
            )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка обработки: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("bot:app", host="127.0.0.1", port=8000, reload=True)
