import sqlite3

def init_database():
    conn = sqlite3.connect("warehouse_bot.db")
    cursor = conn.cursor()

    # 1. Таблица сотрудников и их ролей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,          -- Администратор, Куратор, Оператор
        region_id TEXT               -- Закрепленная АЗС или регион
    )
    """)

    # 2. Таблица общего учета оборудования
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT UNIQUE,         -- Штрих-код устройства
        name TEXT NOT NULL,          -- Монитор, РДМ, КФ, Каскад
        current_location TEXT,       -- Где сейчас (АЗС №, Склад)
        status TEXT NOT NULL,        -- Работает, Неисправен
        issue_description TEXT       -- Описание поломки
    )
    """)

    # 3. Таблица официальных перемещений
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER,
        sender_id INTEGER,
        receiver_id INTEGER,
        status TEXT DEFAULT 'В пути', -- В пути, Получено
        sender_message_id INTEGER,
        receiver_message_id INTEGER,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        received_at TIMESTAMP,
        FOREIGN KEY(inventory_id) REFERENCES inventory(id)
    )
    """)

    # 4. Таблица изолированного учета куратора
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kurator_private_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kurator_id INTEGER,           
        item_name TEXT NOT NULL,
        location_details TEXT,
        comment TEXT
    )
    """)

    # 5. Таблица учета рабочих смен куратором
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS work_shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kurator_id INTEGER,
        worker_name TEXT NOT NULL,
        gas_station TEXT NOT NULL,
        shift_date DATE NOT NULL,
        hours_worked INTEGER NOT NULL
    )
    """)

    # --- ЗАПОЛНЕНИЕ ТЕСТОВЫМИ ДАННЫМИ ---
    # ЗАМЕНИТЕ 123456789 НА ВАШ ТЕЛЕГРАМ ID
    cursor.execute("""
    INSERT OR IGNORE INTO users (telegram_id, name, role, region_id)
    VALUES (123456789, 'Главный Администратор', 'Администратор', 'Все регионы')
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO users (telegram_id, name, role, region_id)
    VALUES (987654321, 'Иван Куратор', 'Куратор', 'АЗС-Регион-Север')
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO inventory (barcode, name, current_location, status, issue_description)
    VALUES ('2000100054321', 'Монитор Каскад', 'АЗС №3', 'Неисправен', 'Полосы на экране, не включается')
    """)

    conn.commit()
    conn.close()
    print("🚀 Успех! База данных warehouse_bot.db создана, тестовые роли зафиксированы.")

if __name__ == "__main__":
    init_database()
