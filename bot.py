import os
import json
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright
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

MOS_LOGIN = os.environ.get("MOS_LOGIN")
MOS_PASSWORD = os.environ.get("MOS_PASSWORD")

DATA_FILE = "waiting_results.json"
CHECK_INTERVAL_SECONDS = 60

ASK_SUBJECT, ASK_GRADE, ASK_DATE, ASK_DIAGNOSTIC = range(4)

PORTFOLIO_URL = "https://school.mos.ru/portfolio/student/study"
OKMCKO_URL = "https://okmcko.mos.ru"

SITES_TO_CHECK = [
    {
        "name": "Портфолио МЭШ",
        "url": PORTFOLIO_URL,
    },
    {
        "name": "ОК МЦКО",
        "url": OKMCKO_URL,
    },
]


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


def normalize_text(text: str) -> str:
    return (
        text.lower()
        .replace("ё", "е")
        .replace("-", " ")
        .replace("—", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace(",", " ")
        .replace(".", " ")
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот проверки результатов МЦКО/МЭШ запущен.\n\n"
        "Команды:\n"
        "➕ /add — добавить диагностику в ожидание\n"
        "📋 /list — показать ожидания\n"
        "🗑 /delete — удалить все ожидания\n"
        "🔎 /check — проверить сейчас\n"
        "🌐 /sites — показать сайты проверки\n"
        "🔐 /auth — проверить, добавлен ли логин mos.ru\n\n"
        "⚠️ Логин и пароль от mos.ru не вводятся в Telegram. "
        "Они должны быть добавлены в Railway Variables."
    )


async def auth_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if MOS_LOGIN and MOS_PASSWORD:
        await update.message.reply_text(
            "✅ Логин и пароль mos.ru добавлены в Railway Variables.\n\n"
            "Бот попробует входить через mos.ru/МЭШ при проверке."
        )
    else:
        await update.message.reply_text(
            "❌ Логин или пароль mos.ru не добавлены.\n\n"
            "В Railway → Variables нужно добавить:\n"
            "MOS_LOGIN\n"
            "MOS_PASSWORD"
        )


async def sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🌐 Бот проверяет сайты:\n\n"

    for i, site in enumerate(SITES_TO_CHECK, start=1):
        text += f"{i}. {site['name']}\n{site['url']}\n\n"

    await update.message.reply_text(text)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Напиши предмет.\n\n"
        "Например:\n"
        "Математика"
    )
    return ASK_SUBJECT


async def ask_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subject"] = update.message.text.strip()
    await update.message.reply_text(
        "🎓 Напиши параллель/класс.\n\n"
        "Например:\n"
        "7"
    )
    return ASK_GRADE


async def ask_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["grade"] = update.message.text.strip()
    await update.message.reply_text(
        "📅 Напиши дату диагностики.\n\n"
        "Например:\n"
        "21.04.2025"
    )
    return ASK_DATE


async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Напиши название диагностики.\n\n"
        "Например:\n"
        "алгебра\n\n"
        "Если на сайте написано «Математика (часть 1 - алгебра)», "
        "сюда лучше писать просто: алгебра"
    )
    return ASK_DIAGNOSTIC


async def ask_diagnostic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    diagnostic = update.message.text.strip()

    item = {
        "chat_id": update.effective_chat.id,
        "subject": context.user_data["subject"],
        "grade": context.user_data["grade"],
        "date": context.user_data["date"],
        "diagnostic": diagnostic,
        "status": "waiting",
    }

    data = load_waiting_results()
    data.append(item)
    save_waiting_results(data)

    await update.message.reply_text(
        "✅ Диагностика добавлена в ожидание.\n\n"
        f"📚 Предмет: {item['subject']}\n"
        f"🎓 Параллель: {item['grade']}\n"
        f"📅 Дата: {item['date']}\n"
        f"📝 Диагностика: {item['diagnostic']}\n\n"
        "⏱ Бот будет проверять её каждую 1 минуту."
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Добавление отменено.")
    return ConversationHandler.END


async def list_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    user_items = [
        item for item in data
        if item.get("chat_id") == chat_id and item.get("status") == "waiting"
    ]

    if not user_items:
        await update.message.reply_text("📭 Сейчас нет диагностик в ожидании.")
        return

    text = "📋 Ожидаемые результаты:\n\n"

    for i, item in enumerate(user_items, start=1):
        text += (
            f"{i}. 📚 {item['subject']} / {item['diagnostic']}\n"
            f"🎓 Параллель: {item['grade']}\n"
            f"📅 Дата: {item['date']}\n\n"
        )

    await update.message.reply_text(text)


async def delete_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    new_data = [
        item for item in data
        if item.get("chat_id") != chat_id
    ]

    save_waiting_results(new_data)

    await update.message.reply_text("🗑 Все ожидания удалены.")


async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Проверяю результаты сейчас...")

    found_count = await scan_results(context.application)

    if found_count == 0:
        await update.message.reply_text(
            "⏳ Пока результатов нет или бот не смог их увидеть.\n\n"
            "Проверь:\n"
            "1. В Railway добавлены MOS_LOGIN и MOS_PASSWORD\n"
            "2. В диагностике правильно указан предмет: например Математика\n"
            "3. Дата указана как на сайте: например 21.04.2025"
        )
    else:
        await update.message.reply_text(f"✅ Найдено результатов: {found_count}")


async def scan_results(app: Application):
    data = load_waiting_results()
    changed = False
    found_count = 0

    for item in data:
        if item.get("status") != "waiting":
            continue

        result = await check_results_on_sites(
            subject=item["subject"],
            grade=item["grade"],
            date=item["date"],
            diagnostic=item["diagnostic"],
        )

        if result["found"]:
            item["status"] = "found"
            changed = True
            found_count += 1

            await app.bot.send_message(
                chat_id=item["chat_id"],
                text=(
                    "🎉 Найдены результаты!\n\n"
                    f"📚 Предмет: {item['subject']}\n"
                    f"🎓 Параллель: {item['grade']}\n"
                    f"📅 Дата: {item['date']}\n"
                    f"📝 Диагностика: {item['diagnostic']}\n\n"
                    f"🌐 Найдено на сайте: {result['site']}\n\n"
                    f"📌 Фрагмент:\n{result['snippet'][:1200]}"
                ),
            )

    if changed:
        save_waiting_results(data)

    return found_count


async def check_results_on_sites(subject, grade, date, diagnostic):
    if not MOS_LOGIN or not MOS_PASSWORD:
        print("❌ Нет MOS_LOGIN или MOS_PASSWORD в Railway Variables")
        return {
            "found": False,
            "site": None,
            "snippet": "",
        }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context = await browser.new_context()
        page = await context.new_page()

        try:
            logged_in = await login_to_mos_if_needed(page)

            if not logged_in:
                print("❌ Не удалось войти в mos.ru/МЭШ")
                await browser.close()
                return {
                    "found": False,
                    "site": None,
                    "snippet": "",
                }

            for site in SITES_TO_CHECK:
                print(f"🌐 Проверяю сайт: {site['name']} — {site['url']}")

                try:
                    await page.goto(site["url"], wait_until="networkidle", timeout=90000)
                    await page.wait_for_timeout(7000)

                    # Немного прокручиваем страницу, чтобы подгрузились карточки.
                    for _ in range(4):
                        await page.mouse.wheel(0, 1200)
                        await page.wait_for_timeout(1500)

                    page_text = await page.locator("body").inner_text(timeout=30000)

                    if is_result_found(
                        page_text=page_text,
                        subject=subject,
                        grade=grade,
                        date=date,
                        diagnostic=diagnostic,
                    ):
                        print(f"✅ Результат найден на сайте: {site['name']}")
                        snippet = make_snippet(page_text, date, diagnostic)

                        await browser.close()

                        return {
                            "found": True,
                            "site": site["name"],
                            "snippet": snippet,
                        }

                except Exception as site_error:
                    print(f"Ошибка проверки сайта {site['name']}:", site_error)

            await browser.close()

            return {
                "found": False,
                "site": None,
                "snippet": "",
            }

        except Exception as e:
            print("❌ Общая ошибка проверки:", e)
            await browser.close()
            return {
                "found": False,
                "site": None,
                "snippet": "",
            }


async def login_to_mos_if_needed(page):
    try:
        await page.goto(PORTFOLIO_URL, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(5000)

        text = await page.locator("body").inner_text(timeout=30000)
        lower = normalize_text(text)

        if "портфолио" in lower and ("учеба" in lower or "учёба" in lower):
            print("✅ Уже вошли в МЭШ")
            return True

        print("🔐 Требуется вход. Пытаюсь войти через mos.ru")

        # Пробуем нажать кнопку входа.
        login_buttons = [
            "Войти",
            "Войти через mos.ru",
            "Войти через МЭШ",
            "Продолжить",
        ]

        for button_text in login_buttons:
            try:
                await page.get_by_text(button_text, exact=False).click(timeout=5000)
                await page.wait_for_timeout(4000)
                break
            except Exception:
                pass

        # Пытаемся заполнить логин.
        login_selectors = [
            "input[name='login']",
            "input[name='username']",
            "input[name='email']",
            "input[type='email']",
            "input[type='text']",
            "input",
        ]

        login_filled = False

        for selector in login_selectors:
            try:
                locator = page.locator(selector).first
                await locator.fill(MOS_LOGIN, timeout=7000)
                login_filled = True
                print("✅ Логин заполнен")
                break
            except Exception:
                pass

        if not login_filled:
            print("❌ Не нашёл поле логина")
            return False

        # Иногда после логина надо нажать Далее.
        for next_text in ["Далее", "Продолжить", "Войти"]:
            try:
                await page.get_by_text(next_text, exact=False).click(timeout=4000)
                await page.wait_for_timeout(3000)
                break
            except Exception:
                pass

        # Пытаемся заполнить пароль.
        password_filled = False

        try:
            await page.locator("input[type='password']").first.fill(MOS_PASSWORD, timeout=10000)
            password_filled = True
            print("✅ Пароль заполнен")
        except Exception:
            print("❌ Не нашёл поле пароля")

        if not password_filled:
            return False

        # Нажимаем вход.
        for enter_text in ["Войти", "Продолжить", "Подтвердить"]:
            try:
                await page.get_by_text(enter_text, exact=False).click(timeout=5000)
                await page.wait_for_timeout(8000)
                break
            except Exception:
                pass

        # Проверяем, не попросили ли код/капчу/подтверждение.
        text_after = await page.locator("body").inner_text(timeout=30000)
        lower_after = normalize_text(text_after)

        blocked_words = [
            "смс",
            "sms",
            "код",
            "captcha",
            "капча",
            "подтвердите",
            "подтверждение",
            "одноразовый",
            "госуслуги",
        ]

        for word in blocked_words:
            if word in lower_after:
                print("⚠️ Сайт просит код/капчу/подтверждение. Автоматически пройти нельзя.")
                return False

        await page.goto(PORTFOLIO_URL, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(6000)

        final_text = await page.locator("body").inner_text(timeout=30000)
        final_lower = normalize_text(final_text)

        if "портфолио" in final_lower or "учеба" in final_lower or "учёба" in final_lower:
            print("✅ Вход выполнен")
            return True

        print("❌ После входа портфолио не открылось")
        return False

    except Exception as e:
        print("❌ Ошибка входа:", e)
        return False


def is_result_found(page_text, subject, grade, date, diagnostic):
    text = normalize_text(page_text)

    subject = normalize_text(subject)
    grade = normalize_text(grade)
    date = normalize_text(date)
    diagnostic = normalize_text(diagnostic)

    checks = []

    # Предмет. Например: математика.
    if subject:
        checks.append(subject in text)

    # Дата. Например: 21 04 2025 после нормализации.
    if date:
        checks.append(date in text)

    # Диагностика. Например: алгебра / геометрия.
    if diagnostic:
        checks.append(diagnostic in text)

    # Параллель может быть на сайте как "7", "7-х классов", "7 класс".
    grade_ok = False
    if grade:
        variants = [
            f"{grade} класс",
            f"{grade} классов",
            f"{grade} х классов",
            f"{grade} ых классов",
            f"{grade}",
        ]
        grade_ok = any(normalize_text(v) in text for v in variants)
        checks.append(grade_ok)

    print(
        "🔎 Проверка слов:",
        {
            "subject": subject,
            "grade": grade,
            "date": date,
            "diagnostic": diagnostic,
            "checks": checks,
        },
    )

    return all(checks)


def make_snippet(page_text, date, diagnostic):
    text_lower = page_text.lower()
    diagnostic_lower = diagnostic.lower()
    date_lower = date.lower()

    positions = []

    if diagnostic_lower in text_lower:
        positions.append(text_lower.find(diagnostic_lower))

    if date_lower in text_lower:
        positions.append(text_lower.find(date_lower))

    if positions:
        pos = min([p for p in positions if p >= 0])
        start = max(0, pos - 300)
        end = min(len(page_text), pos + 900)
        return page_text[start:end]

    return page_text[:1200]


async def auto_scan(app: Application):
    print("✅ Автопроверка запущена. Интервал: 1 минута.")

    while True:
        await scan_results(app)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


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
    app.add_handler(CommandHandler("auth", auth_status))
    app.add_handler(CommandHandler("sites", sites))
    app.add_handler(CommandHandler("list", list_waiting))
    app.add_handler(CommandHandler("delete", delete_waiting))
    app.add_handler(CommandHandler("check", check_now))
    app.add_handler(add_conversation)

    print("✅ Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
