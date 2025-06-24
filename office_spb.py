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
    tg TEXT,
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

def find_nearest_available_date():
    today = datetime.date.today()
    all_places = ["A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2", "B3", "B4", "B5"]
    for delta in range(0, 30):
        check_date = today + datetime.timedelta(days=delta)
        date_str = check_date.strftime("%Y-%m-%d")
        cursor.execute("SELECT place FROM bookings WHERE date=?", (date_str,))
        occupied_places = set(row[0] for row in cursor.fetchall())
        free_places = [place for place in all_places if place not in occupied_places]
        if free_places:
            return check_date.strftime("%d.%m.%Y"), free_places
    return None, []

# --- Обработчики команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Используйте команды:\n"
        "/start - запуск бота,\n"
        "/book ДД.ММ.ГГ место tg - для бронирования,\n"
        "/cancel ДД.ММ.ГГ место - для отмены,\n"
        "/mybookings - для просмотра броней,\n"
        "/friend_book ДД.ММ.ГГ место tg - для бронирования коллеги,\n"
        "/viewbookings ДД.ММ.ГГ - чтобы посмотреть все брони на дату"

    )
    # Отправка картинки Office.png
    try:
        with open("Office.png", "rb") as photo:
            await update.message.reply_photo(photo)
    except FileNotFoundError:
        await update.message.reply_text("Файл Office.png не найден.")

    # Поиск ближайшей даты и свободных мест
    date_str, free_places = find_nearest_available_date()
    if date_str:
        places_list= ", ".join(free_places)
        message= f"Ближайшая дата с доступными местами: {date_str}\nСвободные места: {places_list}"
    else:
        message= "Нет доступных дат в ближайшем месяце."

    await update.message.reply_text(message)

async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Используйте команду /book <дата(ДД.ММ.ГГ)> <место> <tg>"
        )
        return

    date_input = args[0]
    place = args[1].upper()
    tg_value = args[2]

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
    except ValueError:
        await update.message.reply_text("Некорректная дата.")
        return

    today = datetime.date.today()
    if date_obj < today:
        await update.message.reply_text("Невозможно забронировать прошедшую дату.")
        return

    # Проверка занятости места на эту дату
    cursor.execute(
        "SELECT * FROM bookings WHERE date=? AND place=?", (date_str, place)
    )
    if cursor.fetchone():
        await update.message.reply_text(
            f"Место {place} уже занято на {date_input}."
        )
        return

    # Проверка наличия брони у пользователя на эту дату
    cursor.execute(
        "SELECT * FROM bookings WHERE user_id=? AND date=?", (update.message.from_user.id, date_str)
    )
    if cursor.fetchone():
        await update.message.reply_text("У вас уже есть бронь на эту дату.")
        return

    # Вставляем данные с tg как строку
    week_num= get_week_number(date_str)

    cursor.execute(
        "INSERT INTO bookings (user_id, username, name, date, place, guest_of, week, tg) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            update.message.from_user.id,
            update.message.from_user.username or "",
            update.message.from_user.first_name or "",
            date_str,
            place,
            0,
            week_num,
            tg_value
        ),
    )

    conn.commit()

    await update.message.reply_text(f"Бронь на {date_input} ({place}) {tg_value} успешно создана.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
     args= context.args
     if len(args)<2:
         await update.message.reply_text(
             "Используйте команду /cancel <дата(ДД.ММ.ГГ)> <место>"
         )
         return

     date_input = args[0]
     place= args[1].upper()

     match = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", date_input)
     if not match:
         await update.message.reply_text(
             "Некорректный формат даты. Используйте ДД.ММ.ГГ"
         )
         return

     day, month, year_short= match.groups()
     year_full= "20"+ year_short

     try:
         dt= datetime.date(int(year_full), int(month), int(day))
         date_str= dt.strftime("%Y-%m-%d")
         today= datetime.date.today()
         if dt< today:
             await update.message.reply_text("Невозможно отменить прошедшую бронь.")
             return
     except ValueError:
         await update.message.reply_text("Некорректная дата.")
         return

     user_id= update.message.from_user.id

     cursor.execute(
         "SELECT * FROM bookings WHERE user_id=? AND date=? AND place=?",
         (user_id, date_str, place),
     )

     record= cursor.fetchone()

     if not record:
         await update.message.reply_text("У вас нет такой брони.")
         return

     cursor.execute(
         "DELETE FROM bookings WHERE user_id=? AND date=? AND place=?",
         (user_id, date_str, place),
     )

     conn.commit()

     await update.message.reply_text(f"Бронь на {date_input} ({place}) отменена.")

async def mybookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
     user_id= update.message.from_user.id
     cursor.execute("SELECT date, place FROM bookings WHERE user_id=?", (user_id,))
     records= cursor.fetchall()
     if not records:
         await update.message.reply_text("У вас нет текущих броней.")
         return
     message_lines=[]
     for record in records:
         date_iso= record[0]
         place= record[1]
         dt_obj= datetime.datetime.strptime(date_iso,"%Y-%m-%d")
         display_date= dt_obj.strftime("%d.%m.%y")
         message_lines.append(f"{display_date} - {place}")
     message_text="\n".join(message_lines)
     await update.message.reply_text(f"Ваши брони:\n{message_text}")

# Новая функция для просмотра всех броней на дату
async def view_bookings_on_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
     args= context.args
     if len(args)!=1:
         await update.message.reply_text("Используйте команду /viewbookings <дата(ДД.ММ.ГГ)>")
         return

     date_input=args[0]

     # Проверка формата даты
     if not is_valid_date(date_input):
         await update.message.reply_text("Некорректный формат даты. Используйте ДД.ММ.ГГ")
         return

     match=re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$",date_input)
     day,mont,y_short=match.groups()
     year_full="20"+y_short

     try:
         dt=datetime.date(int(year_full),int(mont),int(day))
         date_iso=dt.strftime("%Y-%m-%d")
     except ValueError:
         await update.message.reply_text("Некорректная дата.")
         return

     # Получаем все брони на эту дату
     cursor.execute("SELECT place,tg FROM bookings WHERE date=?", (date_iso,))
     records=cursor.fetchall()

     if not records:
         await update.message.reply_text(f"На {date_input} нет забронированных мест.")
         return

     message_lines=[]
     for place,tg in records:
         message_lines.append(f"{place} {tg}")

     message_text="\n".join(message_lines)
     await update.message.reply_text(f"Бронирования на {date_input}:\n{message_text}")

# Бронирования коллеги

async def friend_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Используйте /friend_book ДД.ММ.ГГ место tg"
        )
        return

    date_str_input = args[0]
    place_target = args[1].upper()
    target_username = args[2]
    tg_username = args[3]

    # Попытка парсинга даты в формате ДД.ММ.ГГ
    try:
        dt = datetime.datetime.strptime(date_str_input, "%d.%m.%y").date()
        target_date_iso = dt.strftime("%Y-%m-%d")
        week_num = get_week_number(target_date_iso)
    except ValueError:
        await update.message.reply_text("Некорректная дата. Используйте формат ДД.ММ.ГГ")
        return

    # Проверка занятости места на эту дату
    cursor.execute(
        "SELECT * FROM bookings WHERE date=? AND place=?", (target_date_iso, place_target)
    )
    if cursor.fetchone():
        await update.message.reply_text(f"Место {place_target} уже занято на {date_str_input}.")
        return

    # Проверка, есть ли у этого пользователя уже бронь на эту дату
    cursor.execute(
        "SELECT * FROM bookings WHERE user_id=? AND date=?", (update.message.from_user.id, target_date_iso)
    )
    if cursor.fetchone():
        await update.message.reply_text("У вас уже есть бронь на эту дату.")
        return

    # Вставляем бронь для коллеги
    cursor.execute(
        "INSERT INTO bookings (user_id, username, name, date, place, guest_of, week, tg) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            None,
            target_username,
            None,  # Можно оставить пустым или указать имя при необходимости
            target_date_iso,
            place_target,
            1,  # guest_of=1 означает что это бронь коллеги
            week_num,
            tg_username  # сохраняем tg как username коллеги
        ),
    )

    conn.commit()

    await update.message.reply_text(
        f"Бронь для ({target_username}) на {date_str_input} ({place_target}) успешно добавлена."
    )

# --- Основная часть запуска бота ---

if __name__ == '__main__':
    TOKEN= "7804867932:AAFgFGwPj9keutfNRc1_ZzLNzpoJ4hOM5fE"  # замените на ваш токен бота

    application= ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("book", book))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("mybookings", mybookings))
    application.add_handler(CommandHandler("viewbookings", view_bookings_on_date))
    application.add_handler(CommandHandler("friend_book", friend_book))

    print("Бот запущен")
    application.run_polling()