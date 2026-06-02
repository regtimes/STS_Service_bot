import sqlite3

def init_database():
    conn = sqlite3.connect("warehouse_bot.db")
    cursor = conn.cursor()

    # Таблица сотрудников, где телефон является главным уникальным ключом
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER,         -- Заполнится автоматически при первом входе
        phone TEXT PRIMARY KEY,      -- Номер телефона в формате 79991234567 (без +)
        name TEXT NOT NULL,          
        role TEXT NOT NULL,          -- Администратор, Куратор, Operator
        region_id TEXT               
    )
    """)

    # =====================================================================
    # ВПИШИТЕ ВАШ РЕАЛЬНЫЙ НОМЕР ТЕЛЕФОНА НИЖЕ (СТРОГО БЕЗ ЗНАКА ПЛЮС)
    # =====================================================================
    YOUR_PHONE = "380933050011"

    cursor.execute("""
    INSERT OR IGNORE INTO users (telegram_id, phone, name, role, region_id)
    VALUES (NULL, ?, 'Главный Администратор', 'Администратор', 'Все регионы')
    """, (YOUR_PHONE,))

    conn.commit()
    conn.close()
    print(f"🚀 База warehouse_bot.db успешно создана!")
    print(f"✅ Номер {YOUR_PHONE} внесен в белый список со статусом Администратор.")

if __name__ == "__main__":
    init_database()
