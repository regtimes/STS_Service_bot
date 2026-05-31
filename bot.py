import sqlite3
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from telebot import TeleBot, types

# 1. Загрузка настроек окружения
load_dotenv()

# Ваша актуальная ссылка ngrok (измените, если в консоли ngrok она другая)
WEBHOOK_URL = "https://frosting-suffix-corporate.ngrok-free.dev/webhook"

TOKEN = os.getenv("TOKEN")
bot = TeleBot(TOKEN)


# 2. Инициализация базы данных sklad.db
def init_db():
    conn = sqlite3.connect("sklad.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            quantity INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


# 3. Функция добавления/обновления товара
def add_to_sklad(name, qty):
    conn = sqlite3.connect("sklad.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO items (name, quantity)
        VALUES (?, ?) ON CONFLICT(name) DO
        UPDATE SET quantity = quantity + ?
    """, (name, qty, qty))
    conn.commit()
    conn.close()


# 4. Менеджер жизненного цикла приложения (вместо устаревшего on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код, который выполняется ПРИ СТАРТЕ сервера
    init_db()
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print("🚀 Сервер и вебхук Telegram успешно настроены через lifespan!")
    yield
    # Код, который выполняется ПРИ ОСТАНОВКЕ сервера (если необходим)


# Передаем управление жизненным циклом в FastAPI
app = FastAPI(lifespan=lifespan)


# 5. Эндпоинт для Mini App (выдача вашей HTML страницы)
@app.get("/", response_class=HTMLResponse)
async def read_item():
    path_to_html = os.path.join(os.path.dirname(__file__), "index.html")
    with open(path_to_html, "r", encoding="utf-8") as file:
        html_content = file.read()
    return HTMLResponse(content=html_content, status_code=200)


# 6. Эндпоинт вебхука, который принимает сообщения от Telegram
@app.post("/webhook")
async def telegram_webhook(request: Request):
    if request.headers.get("content-type") == "application/json":
        json_string = await request.json()
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])  # Передаем текстовые команды боту
        return {"status": "ok"}
    return {"status": "error"}


# =====================================================================
# ОБРАБОТЧИКИ КОМАНД ТЕЛЕГРАМ-БОТА
# =====================================================================

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "Привет! Чтобы добавить товар, напиши: /add Название Количество")


@bot.message_handler(commands=['add'])
def add_cmd(message):
    try:
        parts = message.text.split()
        name = parts[1]  # Добавили [1]
        qty = int(parts[2])  # Добавили [2]

        add_to_sklad(name, qty)
        bot.reply_to(message, f"✅ Успешно добавлено: {name} ({qty} шт.)")
    except Exception:
        bot.reply_to(message, "❌ Ошибка. Пишите так: `/add Кирпич 50`")



@bot.message_handler(commands=['list'])
def list_cmd(message):
    conn = sqlite3.connect("sklad.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, quantity FROM items")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.reply_to(message, "📦 Склад пуст!")
        return

    text = "📋 **Текущие остатки на складе:**\n\n"
    for row in rows:
        text += f"🔹 {row[0]}: {row[1]} шт.\n"  # Добавили [0] и [1]

    bot.reply_to(message, text, parse_mode="Markdown")




# Запуск через зелёную кнопку "Старт" в PyCharm (поднимает uvicorn)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="127.0.0.1", port=8000, reload=True)
