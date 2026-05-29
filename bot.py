import sqlite3
from telebot import TeleBot

# Токен вашего бота от @BotFather
TOKEN = "8090467638:AAEeR5YLb9zPx3L9MqPHbh27mfWuhu0bjZ0"
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


if __name__ == "__main__":
    init_db()  # Запускаем БД
    print("Бот успешно запущен локально...")
    bot.infinity_polling()
