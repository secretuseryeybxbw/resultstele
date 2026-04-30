import os
import json
import asyncio
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

BOT_VERSION = "MESH_OKMCKO_FULL_FIX_V2"

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
MOS_LOGIN = os.environ.get("MOS_LOGIN")
MOS_PASSWORD = os.environ.get("MOS_PASSWORD")

DATA_FILE = "waiting_results.json"
CHECK_INTERVAL_SECONDS = 30

ASK_SUBJECT, ASK_GRADE, ASK_DATE, ASK_DIAGNOSTIC = range(4)

SCHOOL_URL = "https://school.mos.ru/"
PORTFOLIO_URL = "https://school.mos.ru/portfolio/"
OKMCKO_URL = "https://okmcko.mos.ru"

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🔐 Проверить вход"],
        ["📋 Просмотр результатов диагностик"],
        ["🔎 Поиск результата МЦКО"],
        ["➕ Добавить диагностику"],
        ["📄 Список ожиданий", "🗑 Очистить ожидания"],
        ["🌐 Сайты", "🧩 Версия"],
    ],
    resize_keyboard=True,
)


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


async def safe_goto(page, url, timeout=90000):
    for attempt in range(1, 4):
        try:
            print(f"🔗 Открываю: {url} | попытка {attempt}")

            response = await page.goto(
                url,
                wait_until="commit",
                timeout=timeout,
            )

            await page.wait_for_timeout(12000)

            print(f"✅ URL после перехода: {page.url}")

            if response:
                print(f"✅ HTTP status: {response.status}")

            return True

        except Exception as e:
            print(f"⚠️ Ошибка перехода на {url}, попытка {attempt}: {e}")
            await page.wait_for_timeout(5000)

    return False


async def safe_body_text(page, timeout=30000):
    try:
        text = await page.locator("body").inner_text(timeout=timeout)
        if text.strip():
            return text
    except Exception as e:
        print("⚠️ Не смог прочитать body:", e)

    try:
        html = await page.content()
        print("📄 HTML первые 3000 символов:")
        print(html[:3000])
        return html
    except Exception as e2:
        print("⚠️ Не смог прочитать HTML:", e2)
        return ""


async def click_by_text(page, texts, timeout=5000):
    for text in texts:
        try:
            await page.get_by_text(text, exact=False).click(timeout=timeout)
            print(f"✅ Нажал кнопку: {text}")
            await page.wait_for_timeout(3000)
            return True
        except Exception:
            pass

    return False


async def fill_first_visible(page, selectors, value, field_name):
    for selector in selectors:
        try:
            fields = page.locator(selector)
            count = await fields.count()
            print(f"Пробую поле {field_name}: {selector}, найдено: {count}")

            for i in range(count):
                field = fields.nth(i)
                try:
                    if await field.is_visible(timeout=1500):
                        await field.fill(value, timeout=7000)
                        print(f"✅ Поле {field_name} заполнено через {selector}, индекс {i}")
                        return True
                except Exception:
                    pass

        except Exception as e:
            print(f"Не подошёл selector {selector}: {e}")

    print(f"❌ Не найдено поле: {field_name}")
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот проверки результатов МЭШ и ОК МЦКО запущен.\n\n"
        "Выбери действие в меню ниже.\n\n"
        "Проверка ожиданий идёт каждые 30 секунд.",
        reply_markup=MAIN_MENU,
    )


async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🧩 Версия кода: {BOT_VERSION}")


async def auth_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if MOS_LOGIN and MOS_PASSWORD:
        await update.message.reply_text(
            "✅ MOS_LOGIN и MOS_PASSWORD добавлены в Railway Variables.\n\n"
            "Бот будет пробовать входить через school.mos.ru / МЭШ.",
            reply_markup=MAIN_MENU,
        )
    else:
        await update.message.reply_text(
            "❌ Нет MOS_LOGIN или MOS_PASSWORD.\n\n"
            "Добавь в Railway → Variables:\n"
            "MOS_LOGIN\n"
            "MOS_PASSWORD",
            reply_markup=MAIN_MENU,
        )


async def sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Бот проверяет:\n\n"
        f"1. МЭШ / Портфолио:\n{PORTFOLIO_URL}\n\n"
        f"2. ОК МЦКО:\n{OKMCKO_URL}\n\n"
        f"Версия: {BOT_VERSION}",
        reply_markup=MAIN_MENU,
    )


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
        "🎓 Напиши класс/параллель.\n\n"
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
        "⏱ Бот будет проверять её каждые 30 секунд.",
        reply_markup=MAIN_MENU,
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Добавление отменено.", reply_markup=MAIN_MENU)
    return ConversationHandler.END


async def list_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    items = [
        item for item in data
        if item.get("chat_id") == chat_id and item.get("status") == "waiting"
    ]

    if not items:
        await update.message.reply_text("📭 Сейчас нет ожиданий.", reply_markup=MAIN_MENU)
        return

    text = "📋 Ожидаемые результаты:\n\n"

    for i, item in enumerate(items, start=1):
        text += (
            f"{i}. {item['subject']} / {item['diagnostic']}\n"
            f"🎓 Класс: {item['grade']}\n"
            f"📅 Дата: {item['date']}\n\n"
        )

    await update.message.reply_text(text, reply_markup=MAIN_MENU)


async def delete_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_waiting_results()
    chat_id = update.effective_chat.id

    data = [item for item in data if item.get("chat_id") != chat_id]
    save_waiting_results(data)

    await update.message.reply_text("🗑 Все ожидания удалены.", reply_markup=MAIN_MENU)


async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Проверяю МЭШ и ОК МЦКО сейчас...")

    found_count = await scan_results(context.application)

    if found_count == 0:
        await update.message.reply_text(
            "⏳ Пока результат не найден.\n\n"
            "Проверь, что диагностика введена коротко:\n"
            "алгебра\n"
            "геометрия",
            reply_markup=MAIN_MENU,
        )
    else:
        await update.message.reply_text(
            f"✅ Найдено результатов: {found_count}",
            reply_markup=MAIN_MENU,
        )


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "🔐 Проверить вход":
        await auth_status(update, context)
    elif text == "📋 Просмотр результатов диагностик":
        await check_now(update, context)
    elif text == "🔎 Поиск результата МЦКО":
        await check_now(update, context)
    elif text == "📄 Список ожиданий":
        await list_waiting(update, context)
    elif text == "🗑 Очистить ожидания":
        await delete_waiting(update, context)
    elif text == "🌐 Сайты":
        await sites(update, context)
    elif text == "🧩 Версия":
        await version(update, context)
    else:
        await update.message.reply_text(
            "Не понял команду. Выбери действие кнопкой ниже.",
            reply_markup=MAIN_MENU,
        )


async def scan_results(app: Application):
    data = load_waiting_results()
    changed = False
    found_count = 0

    for item in data:
        if item.get("status") != "waiting":
            continue

        result = await check_all_sites(
            diagnostic=item["diagnostic"],
            subject=item["subject"],
            grade=item["grade"],
            date=item["date"],
        )

        if result["found"]:
            item["status"] = "found"
            changed = True
            found_count += 1

            await app.bot.send_message(
                chat_id=item["chat_id"],
                text=(
                    "🎉 Результаты найдены!\n\n"
                    f"📚 Предмет: {item['subject']}\n"
                    f"🎓 Параллель: {item['grade']}\n"
                    f"📅 Дата: {item['date']}\n"
                    f"📝 Диагностика: {item['diagnostic']}\n\n"
                    f"🌐 Найдено на сайте: {result['site']}\n\n"
                    f"📌 Фрагмент:\n{result['snippet'][:1500]}"
                ),
            )

    if changed:
        save_waiting_results(data)

    return found_count


async def check_all_sites(diagnostic, subject, grade, date):
    if not MOS_LOGIN or not MOS_PASSWORD:
        print("❌ Нет MOS_LOGIN или MOS_PASSWORD")
        return {"found": False, "site": "", "snippet": ""}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="ru-RU",
        )

        page = await context.new_page()

        try:
            logged_in = await login_school_mos(page)

            if not logged_in:
                print("❌ Вход в school.mos.ru не выполнен")
                await browser.close()
                return {"found": False, "site": "", "snippet": ""}

            portfolio_result = await check_portfolio(page, diagnostic)
            if portfolio_result["found"]:
                await browser.close()
                return portfolio_result

            okmcko_result = await check_okmcko(page, diagnostic)
            if okmcko_result["found"]:
                await browser.close()
                return okmcko_result

            await browser.close()
            return {"found": False, "site": "", "snippet": ""}

        except Exception as e:
            print("❌ Общая ошибка проверки:", e)
            await browser.close()
            return {"found": False, "site": "", "snippet": ""}


async def login_school_mos(page):
    try:
        print("🔐 Открываю school.mos.ru")
        await safe_goto(page, SCHOOL_URL, timeout=90000)

        text = await safe_body_text(page, timeout=30000)
        lower = normalize_text(text)

        print("📄 Текст school.mos.ru:")
        print(text[:3000])

        if "дневник" in lower or "портфолио" in lower or "учеба" in lower:
            print("✅ Уже авторизован на school.mos.ru")
            return True

        if "access denied" in lower or "forbidden" in lower or "captcha" in lower:
            print("❌ school.mos.ru блокирует Railway / просит защиту")
            return False

        print("🔐 Ищу кнопку входа")

        await click_by_text(
            page,
            [
                "Войти",
                "Войти через mos.ru",
                "Войти через МЭШ",
                "Авторизоваться",
                "Продолжить",
                "ЕЖД",
                "МЭШ",
            ],
            timeout=6000,
        )

        await page.wait_for_timeout(5000)

        print("🔐 Заполняю логин")

        login_ok = await fill_first_visible(
            page,
            [
                "input[name='login']",
                "input[name='username']",
                "input[name='email']",
                "input[name='phone']",
                "input[type='email']",
                "input[type='tel']",
                "input[type='text']",
                "input:not([type])",
                "input",
            ],
            MOS_LOGIN,
            "логин",
        )

        if not login_ok:
            print("❌ Не найдено поле логина")
            return False

        await click_by_text(page, ["Далее", "Продолжить", "Войти"], timeout=5000)

        print("🔐 Заполняю пароль")

        password_ok = await fill_first_visible(
            page,
            [
                "input[type='password']",
                "input[name='password']",
            ],
            MOS_PASSWORD,
            "пароль",
        )

        if not password_ok:
            print("❌ Не найдено поле пароля")
            return False

        await click_by_text(page, ["Войти", "Продолжить", "Подтвердить"], timeout=5000)
        await page.wait_for_timeout(12000)

        after_text = await safe_body_text(page, timeout=30000)
        after_lower = normalize_text(after_text)

        print("📄 Текст после входа:")
        print(after_text[:3000])

        blocked_words = [
            "смс",
            "sms",
            "код",
            "captcha",
            "капча",
            "подтверд",
            "одноразовый",
            "госуслуги",
        ]

        if any(word in after_lower for word in blocked_words):
            print("⚠️ Сайт просит код/подтверждение/капчу. Автоматически пройти нельзя.")
            return False

        if "дневник" in after_lower or "портфолио" in after_lower or "учеба" in after_lower:
            print("✅ Вход выполнен")
            return True

        print("⚠️ Вход мог выполниться, пробую перейти в портфолио")

        await safe_goto(page, PORTFOLIO_URL, timeout=90000)
        await page.wait_for_timeout(10000)

        portfolio_text = await safe_body_text(page, timeout=30000)
        portfolio_lower = normalize_text(portfolio_text)

        if "портфолио" in portfolio_lower or "учеба" in portfolio_lower:
            print("✅ Вход выполнен, портфолио доступно")
            return True

        print("❌ Вход не подтверждён")
        return False

    except Exception as e:
        print("❌ Ошибка входа school.mos.ru:", e)
        return False


async def check_portfolio(page, diagnostic):
    try:
        print("🌐 Проверяю Портфолио МЭШ")
        print(f"🔗 URL: {PORTFOLIO_URL}")
        print(f"📌 Ищу диагностику: {diagnostic}")

        await safe_goto(page, PORTFOLIO_URL, timeout=90000)
        await page.wait_for_timeout(10000)

        for _ in range(20):
            await page.mouse.wheel(0, 1200)
            await page.wait_for_timeout(700)

        page_text = await safe_body_text(page, timeout=30000)

        print("📄 Текст портфолио, первые 5000 символов:")
        print(page_text[:5000])

        if is_result_found(page_text, diagnostic):
            return {
                "found": True,
                "site": "Портфолио МЭШ",
                "snippet": make_snippet(page_text, diagnostic),
            }

        return {"found": False, "site": "", "snippet": ""}

    except Exception as e:
        print("❌ Ошибка проверки Портфолио МЭШ:", e)
        return {"found": False, "site": "", "snippet": ""}


async def check_okmcko(page, diagnostic):
    try:
        print("🌐 Проверяю ОК МЦКО")
        print(f"🔗 URL: {OKMCKO_URL}")
        print(f"📌 Ищу диагностику: {diagnostic}")

        await safe_goto(page, OKMCKO_URL, timeout=90000)
        await page.wait_for_timeout(8000)

        text = await safe_body_text(page, timeout=30000)
        lower = normalize_text(text)

        print("📄 Текст ОК МЦКО до входа:")
        print(text[:3000])

        if "войти" in lower or "мэш" in lower or "mos" in lower:
            await click_by_text(
                page,
                [
                    "Войти через МЭШ",
                    "Войти через mos.ru",
                    "Войти",
                    "Авторизоваться",
                ],
                timeout=6000,
            )
            await page.wait_for_timeout(10000)

        await safe_goto(page, OKMCKO_URL, timeout=90000)
        await page.wait_for_timeout(10000)

        for _ in range(15):
            await page.mouse.wheel(0, 1200)
            await page.wait_for_timeout(700)

        page_text = await safe_body_text(page, timeout=30000)

        print("📄 Текст ОК МЦКО, первые 5000 символов:")
        print(page_text[:5000])

        if is_result_found(page_text, diagnostic):
            return {
                "found": True,
                "site": "ОК МЦКО",
                "snippet": make_snippet(page_text, diagnostic),
            }

        return {"found": False, "site": "", "snippet": ""}

    except Exception as e:
        print("❌ Ошибка проверки ОК МЦКО:", e)
        return {"found": False, "site": "", "snippet": ""}


def is_result_found(page_text, diagnostic):
    text = normalize_text(page_text)
    diagnostic_norm = normalize_text(diagnostic)

    if not diagnostic_norm:
        print("❌ Диагностика пустая")
        return False

    diagnostic_ok = diagnostic_norm in text

    result_words_ok = (
        "результат" in text
        or "баллов" in text
        or "отметка" in text
        or "оценка качества образования" in text
        or "диагностика" in text
    )

    print(
        "🔎 ПРОВЕРКА РЕЗУЛЬТАТА:",
        {
            "diagnostic": diagnostic_norm,
            "diagnostic_ok": diagnostic_ok,
            "result_words_ok": result_words_ok,
            "version": BOT_VERSION,
        },
    )

    return diagnostic_ok and result_words_ok


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
    print(f"✅ Автопроверка запущена. Интервал: 30 секунд. Версия: {BOT_VERSION}")

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
        entry_points=[
            CommandHandler("add", add_start),
            MessageHandler(filters.Regex("^➕ Добавить диагностику$"), add_start),
        ],
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

    app.add_handler(add_conversation)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("version", version))
    app.add_handler(CommandHandler("auth", auth_status))
    app.add_handler(CommandHandler("sites", sites))
    app.add_handler(CommandHandler("list", list_waiting))
    app.add_handler(CommandHandler("delete", delete_waiting))
    app.add_handler(CommandHandler("check", check_now))

    app.add_handler(MessageHandler(filters.Regex("^🔐 Проверить вход$"), auth_status))
    app.add_handler(MessageHandler(filters.Regex("^📋 Просмотр результатов диагностик$"), check_now))
    app.add_handler(MessageHandler(filters.Regex("^🔎 Поиск результата МЦКО$"), check_now))
    app.add_handler(MessageHandler(filters.Regex("^📄 Список ожиданий$"), list_waiting))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Очистить ожидания$"), delete_waiting))
    app.add_handler(MessageHandler(filters.Regex("^🌐 Сайты$"), sites))
    app.add_handler(MessageHandler(filters.Regex("^🧩 Версия$"), version))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    print(f"✅ Бот запущен. Версия: {BOT_VERSION}")
    app.run_polling()


if __name__ == "__main__":
    main()
