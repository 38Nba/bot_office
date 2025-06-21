import datetime
import re
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Настройка базы данных ---
conn = sqlite3.connect("bookings.db")
cursor = conn.cursor()

# Создаем таблицу бронирований, если не существует
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    user_id INTEGER,
    username TEXT,
    name TEXT,
    date TEXT,
    place TEXT,
    guest_of INTEGER DEFAULT 0,
    week INTEGER,
    PRIMARY KEY (user_id, date, place)
)
""")
conn.commit()

# --- Вспомогательные функции ---


def is_valid_date(date_str):
    """Проверяет формат даты ДД.ММ.ГГ"""
    return re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", date_str) is not None


def get_week_number(date_str):
    """Возвращает номер недели для даты в формате ГГГГ-ММ-ДД"""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return dt.isocalendar()[1]


# --- Обработчики команд ---


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Используйте /book <дата(ДД.ММ.ГГ)> <место> для бронирования.\n"
        "Например: /book 25.12.23 A1\n"
        "Чтобы отменить бронь: /cancel <дата(ДД.ММ.ГГ)> <место>\n"
        "Посмотреть свои брони: /mybookings\n"
        "Админские команды доступны только администраторам."
    )


async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Используйте команду /book <дата(ДД.ММ.ГГ)> <место>"
        )
        return

    date_input = args[0]
    place = args[1].upper()

    # Проверка формата даты
    match = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", date_input)
    if not match:
        await update.message.reply_text(
            "Некорректный формат даты. Используйте ДД.ММ.ГГ"
        )
        return

    day, month, year_short = match.groups()
    year_full = "20" + year_short  # предполагаем 2000-2099

    try:
        date_obj = datetime.date(int(year_full), int(month), int(day))
        date_str = date_obj.strftime("%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Некорректная дата.")
        return

    today = datetime.date.today()
    if date_obj < today:
        await update.message.reply_text("Невозможно забронировать прошедшую дату.")
        return

    user_id = update.message.from_user.id

    # Проверка занятости места на эту дату
    cursor.execute("SELECT * FROM bookings WHERE date=? AND place=?", (date_str, place))
    if cursor.fetchone():
        await update.message.reply_text(f"Место {place} уже занято на {date_input}.")
        return

    # Проверка наличия брони у пользователя на эту дату
    cursor.execute(
        "SELECT * FROM bookings WHERE user_id=? AND date=?", (user_id, date_str)
    )
    if cursor.fetchone():
        await update.message.reply_text("У вас уже есть бронь на эту дату.")
        return

    week_num = get_week_number(date_str)

    # Добавление брони
    cursor.execute(
        "INSERT INTO bookings (user_id, username, name, date, place, guest_of, week) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            update.message.from_user.username or "",
            update.message.from_user.first_name or "",
            date_str,
            place,
            0,
            week_num,
        ),
    )
    conn.commit()

    await update.message.reply_text(f"Бронь на {date_input} ({place}) успешно создана.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Используйте команду /cancel <дата(ДД.ММ.ГГ)> <место>"
        )
        return

    date_input = args[0]
    place = args[1].upper()

    match = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", date_input)

    if not match:
        await update.message.reply_text(
            "Некорректный формат даты. Используйте ДД.ММ.ГГ"
        )
        return

    day, month, year_short = match.groups()

    year_full = "20" + year_short

    try:
        date_obj = datetime.date(int(year_full), int(month), int(day))
        date_str = date_obj.strftime("%Y-%m-%d")

        today = datetime.date.today()
        if date_obj < today:
            await update.message.reply_text("Невозможно отменить прошедшую бронь.")
            return

    except ValueError:
        await update.message.reply_text("Некорректная дата.")
        return

    user_id = update.message.from_user.id

    # Проверка существования брони у пользователя
    cursor.execute(
        "SELECT * FROM bookings WHERE user_id=? AND date=? AND place=?",
        (user_id, date_str, place),
    )

    record = cursor.fetchone()

    if not record:
        await update.message.reply_text("У вас нет такой брони.")
        return

    # Удаление брони
    cursor.execute(
        "DELETE FROM bookings WHERE user_id=? AND date=? AND place=?",
        (user_id, date_str, place),
    )

    conn.commit()

    await update.message.reply_text(f"Бронь на {date_input} ({place}) отменена.")


async def mybookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    cursor.execute("SELECT date, place FROM bookings WHERE user_id=?", (user_id,))

    records = cursor.fetchall()

    if not records:
        await update.message.reply_text("У вас нет текущих броней.")
        return

    message_lines = []
    for record in records:
        date_str_iso = record[0]
        place = record[1]
        dt_obj = datetime.datetime.strptime(date_str_iso, "%Y-%m-%d")
        display_date = dt_obj.strftime("%d.%m.%y")
        message_lines.append(f"{display_date} - {place}")

    message_text = "\n".join(message_lines)
    await update.message.reply_text(f"Ваши брони:\n{message_text}")


# --- Админская команда для добавления брони (/admin_book) ---
async def admin_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_ids = [210993]  # вставьте свои id админов сюда

    user_id_admins = [update.effective_user.id]

    if not any(uid in admin_ids for uid in user_id_admins):
        await update.message.reply_text("Нет прав для этой команды.")
        return

    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Используйте /admin_book <телеграмм_ник> <имя> <дата(ДД.ММ.ГГ)> <место>"
        )
        return

    target_username = args[0]
    name_target = args[1]
    date_str_input = args[2]
    place_target = args[3].upper()

    # Проверка формата даты
    if not is_valid_date(date_str_input):
        await update.message.reply_text("Некорректная дата. Используйте ДД.ММ.ГГ")
        return

    day, month, year_short = re.match(
        r"^(\d{2})\.(\d{2})\.(\d{2})$", date_str_input
    ).groups()
    year_full = "20" + year_short

    try:
        dt_target = datetime.date(int(year_full), int(month), int(day))
        target_date_iso = dt_target.strftime("%Y-%m-%d")
        week_num = get_week_number(target_date_iso)
    except ValueError:
        await update.message.reply_text("Некорректная дата.")
        return

    # Вставляем бронь для другого пользователя — по вашему сценарию.
    # Можно искать пользователя по никнейму или просто вставлять как есть.

    cursor.execute(
        """INSERT OR REPLACE INTO bookings (user_id, username, name, date, place, guest_of, week)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (0, target_username, name_target, target_date_iso, place_target, 0, week_num),
    )

    conn.commit()

    await update.message.reply_text(
        f"Бронь для {name_target} ({target_username}) добавлена на {date_str_input} в место {place_target}."
    )


# --- Основная функция запуска бота ---
def main():
    application = ApplicationBuilder().token("7804867932:AAFgFGwPj9keutfNRc1_ZzLNzpoJ4hOM5fE").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("book", book))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler('mybookings', mybookings))

    # Админская команда
    application.add_handler(CommandHandler('admin_book', admin_book))

    application.run_polling()

if __name__=='__main__':
    main()