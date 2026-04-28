import os
import json
import asyncio
import subprocess
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

BOT_VERSION = "MESH_ONLY_DOMCONTENT_FIX"

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
MOS_LOGIN = os.environ.get("MOS_LOGIN")
MOS_PASSWORD = os.environ.get("MOS_PASSWORD")

DATA_FILE = "waiting_results.json"
CHECK_INTERVAL_SECONDS = 60

ASK_SUBJECT, ASK_GRADE, ASK_DATE, ASK_DIAGNOSTIC = range(4)

PORTFOLIO_URL = "https://school.mos.ru/portfolio/student/study"


def install_playwright_browsers():
    try:
        print("🔧 Проверяю браузеры Playwright...")
        subprocess.run(
            ["python", "-m", "playwright", "install", "--with-deps", "chromium"],
            check=False,
        )
        print("✅ Проверка Playwright завершена")
    except Exception as e:
        print("⚠️ Не удалось выполнить установку Playwright:", e)


def normalize_text(text: str) -> str:
    return (
        str(text)
        .lower()
        .replace("ё", "е")
        .replace("-", " ")
        .replace("—", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace(",", " ")
        .replace(".", " ")
        .replace(":", " ")
        .replace("/", " ")
        .replace("\\", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )


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


async def safe_goto(page, url, timeout=30000):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        return True
    except Exception as e:
        print(f"⚠️ Ошибка перехода на {url}: {e}")
        return False


async def safe_body_text(page, timeout=12000):
    try:
        return await page.locator("body").inner_text(timeout=timeout)
    except Exception as e:
        print("⚠️ Не смог прочитать body:", e)
        return ""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот проверки результатов МЭШ запущен.\n\n"
        "Проверяется только Портфолио МЭШ.\n\n"
        "Команды:\n"
        "➕ /add — добавить диагностику\n"
        "📋 /list — показать ожидания\n"
        "🗑 /delete — удалить ожидания\n"
        "🔎 /check — проверить сейчас\n"
        "🌐 /sites — сайт проверки\n"
        "🔐 /auth — проверить логин mos.ru\n"
        "🧩 /version — версия кода\n\n"
        "⏱ Проверка идёт каждую 1 минуту."
    )


async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Версия кода: {BOT_VERSION}")


async def auth_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if MOS_LOGIN and MOS_PASSWORD:
        await update.message.reply_text(
            "✅ MOS_LOGIN и MOS_PASSWORD добавлены.\n"
            "Бот будет пробовать входить через mos.ru/МЭШ."
        )
    else:
        await update.message.reply_text(
            "❌ Нет MOS_LOGIN или MOS_PASSWORD.\n\n"
            "Добавь их в Railway → Variables:\n"
            "MOS_LOGIN\n"
            "MOS_PASSWORD"
        )


async def sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Бот проверяет только Портфолио МЭШ:\n\n"
        "https://school.mos.ru/portfolio/student/study\n\n"
        f"Версия: {BOT_VERSION}"
    )


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📚 Напиши предмет. Например: Математика")
    return ASK_SUBJECT


async def ask_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["subject"] = update.message.text.strip()
    await update.message.reply_text("🎓 Напиши класс/параллель. Например: 7")
    return ASK_GRADE


async def ask_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["grade"] = update.message.text.strip()
    await update.message.reply_text("📅 Напиши дату. Например: 21.04.2025")
    return ASK_DATE


async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Напиши диагностику.\n\n"
        "Например:\n"
        "алгебра\n"
        "геометрия"
    )
    return ASK_DIAGNOSTIC


async def ask_diagnostic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = {
        "chat_id": update.effective_chat.id,
        "subject": context.user_data["subject"],
        "grade": context.user_data["grade"],
        "date": context.user_data["date"],
        "diagnostic": update.message.text.strip(),
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
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


async def list_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    items = [
        item for item in data
        if item.get("chat_id") == chat_id and item.get("status") == "waiting"
    ]

    if not items:
        await update.message.reply_text("📭 Сейчас нет ожиданий.")
        return

    text = "📋 Ожидаемые результаты:\n\n"

    for i, item in enumerate(items, start=1):
        text += (
            f"{i}. {item['subject']} / {item['diagnostic']}\n"
            f"🎓 Класс: {item['grade']}\n"
            f"📅 Дата: {item['date']}\n\n"
        )

    await update.message.reply_text(text)


async def delete_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    data = [item for item in data if item.get("chat_id") != chat_id]
    save_waiting_results(data)

    await update.message.reply_text("🗑 Все ожидания удалены.")


async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Проверяю Портфолио МЭШ сейчас...")

    found_count = await scan_results(context.application)

    if found_count == 0:
        await update.message.reply_text(
            "⏳ Пока результат по диагностике не найден.\n\n"
            "Проверь, что диагностика введена коротко:\n"
            "алгебра\n"
            "геометрия\n\n"
            f"Версия: {BOT_VERSION}"
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

        result = await check_result_in_portfolio(diagnostic=item["diagnostic"])

        if result["found"]:
            item["status"] = "found"
            changed = True
            found_count += 1

            await app.bot.send_message(
                chat_id=item["chat_id"],
                text=(
                    "🎉 Найден результат по диагностике!\n\n"
                    f"📚 Предмет: {item['subject']}\n"
                    f"🎓 Параллель: {item['grade']}\n"
                    f"📅 Дата: {item['date']}\n"
                    f"📝 Диагностика: {item['diagnostic']}\n\n"
                    "🌐 Найдено в Портфолио МЭШ.\n\n"
                    f"📌 Фрагмент:\n{result['snippet'][:1500]}"
                ),
            )

    if changed:
        save_waiting_results(data)

    return found_count


async def check_result_in_portfolio(diagnostic):
    if not MOS_LOGIN or not MOS_PASSWORD:
        print("❌ Нет MOS_LOGIN или MOS_PASSWORD")
        return {"found": False, "snippet": ""}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )

        context = await browser.new_context()
        page = await context.new_page()

        try:
            logged_in = await login_to_mos(page)

            if not logged_in:
                print("❌ Вход в mos.ru/МЭШ не выполнен")
                await browser.close()
                return {"found": False, "snippet": ""}

            print("🌐 Проверяю только Портфолио МЭШ")
            print(f"📌 Ищу диагностику: {diagnostic}")

            await safe_goto(page, PORTFOLIO_URL, timeout=30000)
            await page.wait_for_timeout(8000)

            for _ in range(15):
                await page.mouse.wheel(0, 1200)
                await page.wait_for_timeout(800)

            page_text = await safe_body_text(page, timeout=15000)

            print("📄 Текст страницы, первые 5000 символов:")
            print(page_text[:5000])

            if is_result_found_by_diagnostic(page_text, diagnostic):
                snippet = make_snippet(page_text, diagnostic)
                await browser.close()
                return {"found": True, "snippet": snippet}

            await browser.close()
            return {"found": False, "snippet": ""}

        except Exception as e:
            print("❌ Ошибка проверки Портфолио МЭШ:", e)
            await browser.close()
            return {"found": False, "snippet": ""}


async def login_to_mos(page):
    try:
        print("🔐 Открываю Портфолио МЭШ")

        await safe_goto(page, PORTFOLIO_URL, timeout=30000)
        await page.wait_for_timeout(5000)

        text = await safe_body_text(page, timeout=12000)
        lower = normalize_text(text)

        print("📄 Первый текст страницы:")
        print(text[:1500])

        if "портфолио" in lower and "учеба" in lower:
            print("✅ Уже авторизован")
            return True

        print("🔐 Ищу кнопку входа")

        login_texts = [
            "Войти",
            "Войти через mos.ru",
            "Войти через МЭШ",
            "Авторизоваться",
            "Продолжить",
        ]

        for txt in login_texts:
            try:
                await page.get_by_text(txt, exact=False).click(timeout=5000)
                await page.wait_for_timeout(4000)
                print(f"✅ Нажал кнопку: {txt}")
                break
            except Exception:
                pass

        print("🔐 Заполняю логин")

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
                field = page.locator(selector).first
                await field.fill(MOS_LOGIN, timeout=7000)
                login_filled = True
                print(f"✅ Логин заполнен через {selector}")
                break
            except Exception:
                pass

        if not login_filled:
            print("❌ Не найдено поле логина")
            return False

        for txt in ["Далее", "Продолжить", "Войти"]:
            try:
                await page.get_by_text(txt, exact=False).click(timeout=4000)
                await page.wait_for_timeout(4000)
                print(f"✅ Нажал после логина: {txt}")
                break
            except Exception:
                pass

        print("🔐 Заполняю пароль")

        try:
            await page.locator("input[type='password']").first.fill(
                MOS_PASSWORD,
                timeout=10000,
            )
            print("✅ Пароль заполнен")
        except Exception:
            print("❌ Не найдено поле пароля")
            return False

        for txt in ["Войти", "Продолжить", "Подтвердить"]:
            try:
                await page.get_by_text(txt, exact=False).click(timeout=5000)
                await page.wait_for_timeout(8000)
                print(f"✅ Нажал вход: {txt}")
                break
            except Exception:
                pass

        print("🔁 Перехожу обратно в Портфолио МЭШ")

        await safe_goto(page, PORTFOLIO_URL, timeout=30000)
        await page.wait_for_timeout(8000)

        final_text = await safe_body_text(page, timeout=15000)
        final_lower = normalize_text(final_text)

        print("📄 Текст после входа:")
        print(final_text[:1500])

        if "портфолио" in final_lower or "учеба" in final_lower:
            print("✅ Вход выполнен")
            return True

        print("❌ Портфолио после входа не открылось")
        return False

    except Exception as e:
        print("❌ Ошибка входа:", e)
        return False


def is_result_found_by_diagnostic(page_text, diagnostic):
    text = normalize_text(page_text)
    diagnostic_norm = normalize_text(diagnostic)

    if not diagnostic_norm:
        print("❌ Диагностика пустая")
        return False

    diagnostic_ok = diagnostic_norm in text

    print(
        "🔎 ПРОВЕРКА ПО ДИАГНОСТИКЕ:",
        {
            "diagnostic": diagnostic_norm,
            "diagnostic_ok": diagnostic_ok,
            "version": BOT_VERSION,
        },
    )

    return diagnostic_ok


def make_snippet(page_text, diagnostic):
    lower = page_text.lower()
    diagnostic_lower = diagnostic.lower()

    if diagnostic_lower in lower:
        pos = lower.find(diagnostic_lower)
        start = max(0, pos - 500)
        end = min(len(page_text), pos + 1200)
        return page_text[start:end]

    return page_text[:1500]


async def auto_scan(app: Application):
    print(f"✅ Автопроверка запущена. Интервал: 1 минута. Версия: {BOT_VERSION}")

    while True:
        await scan_results(app)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def post_init(app: Application):
    asyncio.create_task(auto_scan(app))


def main():
    install_playwright_browsers()

    app = (
        Application.builder()
        .token(TG_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    add_conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_subject)],
            ASK_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_grade)],
            ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            ASK_DIAGNOSTIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_diagnostic)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("version", version))
    app.add_handler(CommandHandler("auth", auth_status))
    app.add_handler(CommandHandler("sites", sites))
    app.add_handler(CommandHandler("list", list_waiting))
    app.add_handler(CommandHandler("delete", delete_waiting))
    app.add_handler(CommandHandler("check", check_now))
    app.add_handler(add_conversation)

    print(f"✅ Бот запущен. Версия: {BOT_VERSION}")
    app.run_polling()


if __name__ == "__main__":
    main()
