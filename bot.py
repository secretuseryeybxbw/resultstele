import os
import json
import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]

DATA_FILE = "waiting_results.json"

ASK_SUBJECT, ASK_GRADE, ASK_DATE, ASK_DIAGNOSTIC = range(4)


def load_waiting_results():
    if not Path(DATA_FILE).exists():
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def save_waiting_results(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот проверки результатов запущен.\n\n"
        "Команды:\n"
        "/add — добавить диагностику в ожидание\n"
        "/list — показать ожидаемые результаты\n"
        "/delete — удалить все ожидания\n"
        "/check — проверить сейчас"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши предмет. Например: Математика")
    return ASK_SUBJECT


async def ask_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subject"] = update.message.text.strip()
    await update.message.reply_text("Напиши параллель/класс. Например: 8")
    return ASK_GRADE


async def ask_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["grade"] = update.message.text.strip()
    await update.message.reply_text("Напиши дату диагностики. Например: 21.04.2026")
    return ASK_DATE


async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text.strip()
    await update.message.reply_text("Напиши название диагностики. Например: Алгебра")
    return ASK_DIAGNOSTIC


async def ask_diagnostic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    diagnostic = update.message.text.strip()

    item = {
        "chat_id": update.effective_chat.id,
        "subject": context.user_data["subject"],
        "grade": context.user_data["grade"],
        "date": context.user_data["date"],
        "diagnostic": diagnostic,
        "status": "waiting"
    }

    data = load_waiting_results()
    data.append(item)
    save_waiting_results(data)

    await update.message.reply_text(
        "Диагностика добавлена в ожидание.\n\n"
        f"Предмет: {item['subject']}\n"
        f"Параллель: {item['grade']}\n"
        f"Дата: {item['date']}\n"
        f"Диагностика: {item['diagnostic']}\n\n"
        "Теперь бот будет проверять результаты каждые 2 минуты."
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END


async def list_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    user_items = [
        item for item in data
        if item["chat_id"] == chat_id and item["status"] == "waiting"
    ]

    if not user_items:
        await update.message.reply_text("Сейчас нет диагностик в ожидании.")
        return

    text = "Ожидаемые результаты:\n\n"

    for i, item in enumerate(user_items, start=1):
        text += (
            f"{i}. {item['subject']} / {item['diagnostic']}\n"
            f"Параллель: {item['grade']}\n"
            f"Дата: {item['date']}\n\n"
        )

    await update.message.reply_text(text)


async def delete_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    new_data = [
        item for item in data
        if item["chat_id"] != chat_id
    ]

    save_waiting_results(new_data)

    await update.message.reply_text("Все ожидания удалены.")


async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Проверяю результаты сейчас...")

    found_count = await scan_results(context.application)

    if found_count == 0:
        await update.message.reply_text("Пока результатов нет. Добавлено в ожидание.")
    else:
        await update.message.reply_text(f"Найдено результатов: {found_count}")


async def scan_results(app: Application):
    data = load_waiting_results()
    changed = False
    found_count = 0

    for item in data:
        if item.get("status") != "waiting":
            continue

        result_found = await check_results_on_site(
            subject=item["subject"],
            grade=item["grade"],
            date=item["date"],
            diagnostic=item["diagnostic"]
        )

        if result_found:
            item["status"] = "found"
            changed = True
            found_count += 1

            await app.bot.send_message(
                chat_id=item["chat_id"],
                text=(
                    "Найдены результаты!\n\n"
                    f"Предмет: {item['subject']}\n"
                    f"Параллель: {item['grade']}\n"
                    f"Дата: {item['date']}\n"
                    f"Диагностика: {item['diagnostic']}"
                )
            )

    if changed:
        save_waiting_results(data)

    return found_count


async def check_results_on_site(subject, grade, date, diagnostic):
    """
    Сюда потом вставляется реальная проверка сайта.

    Сейчас функция всегда возвращает False,
    то есть бот будет считать, что результатов пока нет.

    Когда будет точная ссылка на сайт с результатами,
    сюда добавим код, который проверяет:
    предмет + параллель + дату + диагностику.
    """

    print(
        "Проверка:",
        subject,
        grade,
        date,
        diagnostic
    )

    return False


async def auto_scan(app: Application):
    while True:
        await scan_results(app)
        await asyncio.sleep(120)


async def post_init(app: Application):
    asyncio.create_task(auto_scan(app))


def main():
    app = (
        Application.builder()
        .token(TG_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    add_conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_SUBJECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_subject)
            ],
            ASK_GRADE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_grade)
            ],
            ASK_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)
            ],
            ASK_DIAGNOSTIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_diagnostic)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_waiting))
    app.add_handler(CommandHandler("delete", delete_waiting))
    app.add_handler(CommandHandler("check", check_now))
    app.add_handler(add_conversation)

    print("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
