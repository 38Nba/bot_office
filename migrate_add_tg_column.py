import sqlite3

def migrate_add_tg_column():
    conn = sqlite3.connect("bookings.db")
    cursor = conn.cursor()

    # Проверяем наличие колонки tg
    cursor.execute("PRAGMA table_info(bookings)")
    columns = [info[1] for info in cursor.fetchall()]

    if "tg" not in columns:
        print("Добавляем колонку 'tg' в таблицу 'bookings'...")
        # Выполняем миграцию через executescript()
        script = """
        PRAGMA foreign_keys=off;

        BEGIN TRANSACTION;

        CREATE TABLE IF NOT EXISTS bookings_new (
            user_id INTEGER,
            username TEXT,
            name TEXT,
            date TEXT,
            place TEXT,
            guest_of INTEGER DEFAULT 0,
            week INTEGER,
            tg TEXT
        );

        INSERT INTO bookings_new (user_id, username, name, date, place, guest_of, week)
        SELECT user_id, username, name, date, place, guest_of, week FROM bookings;

        DROP TABLE bookings;

        ALTER TABLE bookings_new RENAME TO bookings;

        COMMIT;
        PRAGMA foreign_keys=on;
        """
        cursor.executescript(script)
        conn.commit()
        print("Миграция завершена успешно.")
    else:
        print("Колонка 'tg' уже существует. Миграция не требуется.")

    conn.close()

# Запуск функции миграции
if __name__ == "__main__":
    migrate_add_tg_column()