import sqlite3
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import os
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv() # Загружает данные из файла .env

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def read_item():
    # Находим путь к вашему файлу index.html
    path_to_html = os.path.join(os.path.dirname(__file__), "index.html")

    with open(path_to_html, "r", encoding="utf-8") as file:
        html_content = file.read()

    return HTMLResponse(content=html_content, status_code=200)



TOKEN = os.getenv("TOKEN") # Безопасно берет токен из системы
bot = TeleBot(TOKEN)



# 1. Инициализация базы данных склад.db
def init_db():
    conn = sqlite3.connect("sklad.db")
    cursor = conn.cursor()
    # Создаем таблицу товаров, если её еще нет
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS items
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       UNIQUE,
                       quantity
                       INTEGER
                       DEFAULT
                       0
                   )
                   """)
    conn.commit()
    conn.close()


# 2. Функция добавления/обновления товара
def add_to_sklad(name, qty):
    conn = sqlite3.connect("sklad.db")
    cursor = conn.cursor()
    # Если товар есть — прибавим количество, если нет — создадим
    cursor.execute("""
                   INSERT INTO items (name, quantity)
                   VALUES (?, ?) ON CONFLICT(name) DO
                   UPDATE SET quantity = quantity + ?
                   """, (name, qty, qty))
    conn.commit()
    conn.close()


# Обработка команды /start
@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "Привет! Чтобы добавить товар, напиши: /add Название Количество")


# Обработка команды /add (например: /add Коробки 15)
@bot.message_handler(commands=['add'])
def add_cmd(message):
    try:
        parts = message.text.split()  # Разрезает строку "/add Кирпич 50" по пробелам
        name = parts[1]  # Берет второе слово (название товара)
        qty = int(parts[2])  # Берет третье слово (количество) и делает его числом

        add_to_sklad(name, qty)
        bot.reply_to(message, f"✅ Успешно добавлено: {name} ({qty} шт.)")
    except Exception:
        bot.reply_to(message, "❌ Ошибка. Пишите так: `/add Кирпич 50`")



# Обработка команды /list для просмотра всего склада
@bot.message_handler(commands=['list'])
def list_cmd(message):
    conn = sqlite3.connect("sklad.db")
    cursor = conn.cursor()
    # Выбираем все товары из таблицы items
    cursor.execute("SELECT name, quantity FROM items")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.reply_to(message, "📦 Склад пуст!")
        return

    # Формируем красивый текст списка
    text = "📋 **Текущие остатки на складе:**\n\n"
    for row in rows:
        text += f"🔹 {row[0]}: {row[1]} шт.\n"

    bot.reply_to(message, text, parse_mode="Markdown")



if __name__ == "__main__":
    init_db()  # Запускаем БД
    print("Бот успешно запущен локально...")
    bot.infinity_polling()


