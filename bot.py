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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Бот проверки результатов МЦКО/МЭШ запущен.\n\n"
        "Команды:\n"
        "➕ /add — добавить диагностику\n"
        "📋 /list — показать ожидания\n"
        "🗑 /delete — удалить ожидания\n"
        "🔎 /check — проверить сейчас\n"
        "🌐 /sites — сайты проверки\n"
        "🔐 /auth — проверить логин mos.ru\n\n"
        "⏱ Проверка идёт каждую 1 минуту."
    )


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
        "🌐 Бот проверяет:\n\n"
        "1. Портфолио МЭШ\n"
        "https://school.mos.ru/portfolio/student/study\n\n"
        "2. ОК МЦКО\n"
        "https://okmcko.mos.ru"
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
        "📅 Напиши дату.\n\n"
        "Например:\n"
        "21.04.2025"
    )
    return ASK_DATE


async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Напиши диагностику.\n\n"
        "Например:\n"
        "алгебра\n\n"
        "Если на сайте написано «Математика (часть 1 - алгебра)», "
        "сюда лучше писать просто: алгебра"
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
    await update.message.reply_text("🔎 Проверяю сейчас...")

    found_count = await scan_results(context.application)

    if found_count == 0:
        await update.message.reply_text(
            "⏳ Пока результатов нет или бот не смог их увидеть.\n\n"
            "Для твоего примера добавляй так:\n"
            "Предмет: Математика\n"
            "Класс: 7\n"
            "Дата: 21.04.2025\n"
            "Диагностика: алгебра"
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
                    f"📌 Фрагмент:\n{result['snippet'][:1500]}"
                ),
            )

    if changed:
        save_waiting_results(data)

    return found_count


async def check_results_on_sites(subject, grade, date, diagnostic):
    if not MOS_LOGIN or not MOS_PASSWORD:
        print("❌ Нет MOS_LOGIN или MOS_PASSWORD")
        return {"found": False, "site": None, "snippet": ""}

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
            logged_in = await login_to_mos(page)

            if not logged_in:
                print("❌ Вход в mos.ru/МЭШ не выполнен")
                await browser.close()
                return {"found": False, "site": None, "snippet": ""}

            for site in SITES_TO_CHECK:
                print(f"🌐 Проверяю {site['name']} — {site['url']}")

                try:
                    await page.goto(site["url"], wait_until="networkidle", timeout=90000)
                    await page.wait_for_timeout(8000)

                    # Прокручиваем страницу, чтобы подгрузились карточки результатов.
                    for _ in range(10):
                        await page.mouse.wheel(0, 1200)
                        await page.wait_for_timeout(1200)

                    page_text = await page.locator("body").inner_text(timeout=30000)

                    print("📄 Текст страницы, первые 3000 символов:")
                    print(page_text[:3000])

                    if is_result_found(page_text, subject, grade, date, diagnostic):
                        snippet = make_snippet(page_text, date, diagnostic)
                        await browser.close()

                        return {
                            "found": True,
                            "site": site["name"],
                            "snippet": snippet,
                        }

                except Exception as e:
                    print(f"Ошибка проверки {site['name']}:", e)

            await browser.close()
            return {"found": False, "site": None, "snippet": ""}

        except Exception as e:
            print("❌ Ошибка:", e)
            await browser.close()
            return {"found": False, "site": None, "snippet": ""}


async def login_to_mos(page):
    try:
        print("🔐 Открываю портфолио МЭШ")

        await page.goto(PORTFOLIO_URL, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(6000)

        text = await page.locator("body").inner_text(timeout=30000)
        lower = normalize_text(text)

        if "портфолио" in lower and ("учеба" in lower or "учёба" in lower):
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

        clicked_login = False

        for txt in login_texts:
            try:
                await page.get_by_text(txt, exact=False).click(timeout=5000)
                await page.wait_for_timeout(5000)
                print(f"✅ Нажал кнопку: {txt}")
                clicked_login = True
                break
            except Exception:
                pass

        if not clicked_login:
            print("⚠️ Кнопку входа не нашёл, пробую искать поля сразу")

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
                await page.wait_for_timeout(9000)
                print(f"✅ Нажал вход: {txt}")
                break
            except Exception:
                pass

        after_text = await page.locator("body").inner_text(timeout=30000)
        after_lower = normalize_text(after_text)

        if "портфолио" in after_lower or "учеба" in after_lower or "учёба" in after_lower:
            print("✅ Вход выполнен")
            return True

        await page.goto(PORTFOLIO_URL, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(7000)

        final_text = await page.locator("body").inner_text(timeout=30000)
        final_lower = normalize_text(final_text)

        if "портфолио" in final_lower or "учеба" in final_lower or "учёба" in final_lower:
            print("✅ Вход выполнен после перехода")
            return True

        print("❌ Портфолио после входа не открылось")
        print(final_text[:1500])
        return False

    except Exception as e:
        print("❌ Ошибка входа:", e)
        return False


def is_result_found(page_text, subject, grade, date, diagnostic):
    text = normalize_text(page_text)

    subject_norm = normalize_text(subject)
    grade_norm = normalize_text(grade)
    date_raw = str(date).strip().lower()
    diagnostic_norm = normalize_text(diagnostic)

    # Очень мягкая проверка:
    # ищем введённую диагностику: алгебра / геометрия / другое слово.
    diagnostic_ok = False
    if diagnostic_norm:
        diagnostic_variants = [
            diagnostic_norm,
            diagnostic_norm.replace("е", "е"),
            diagnostic_norm.replace("ё", "е"),
        ]
        diagnostic_ok = any(v in text for v in diagnostic_variants)

    # Дата проверяется и выводится в лог, но НЕ блокирует результат.
    date_ok = False
    if date_raw:
        date_variants = [
            date_raw,
            date_raw.replace(".", " "),
            date_raw.replace("-", " "),
            date_raw.replace("/", " "),
        ]

        for variant in date_variants:
            if normalize_text(variant) in text or variant in str(page_text).lower():
                date_ok = True
                break

    # Проверяем, что страница похожа на страницу результатов.
    result_page_ok = (
        "результат" in text
        or "твои результат" in text
        or "твой результат" in text
        or "оценка качества образования" in text
        or "баллов" in text
        or "отметка" in text
    )

    # Класс и предмет только для логов.
    subject_ok = subject_norm in text if subject_norm else True

    grade_ok = True
    if grade_norm:
        grade_variants = [
            f"{grade_norm} класс",
            f"{grade_norm} классов",
            f"{grade_norm} х классов",
            f"{grade_norm} ых классов",
            grade_norm,
        ]
        grade_ok = any(normalize_text(v) in text for v in grade_variants)

    print(
        "🔎 МЯГКАЯ ПРОВЕРКА:",
        {
            "subject": subject_norm,
            "subject_ok": subject_ok,
            "grade": grade_norm,
            "grade_ok": grade_ok,
            "date": date_raw,
            "date_ok": date_ok,
            "diagnostic": diagnostic_norm,
            "diagnostic_ok": diagnostic_ok,
            "result_page_ok": result_page_ok,
        },
    )

    # Результат найден, если есть диагностика и страница похожа на страницу результатов.
    return diagnostic_ok and result_page_ok


def make_snippet(page_text, date, diagnostic):
    lower = page_text.lower()
    positions = []

    if diagnostic and diagnostic.lower() in lower:
        positions.append(lower.find(diagnostic.lower()))

    if date and date.lower() in lower:
        positions.append(lower.find(date.lower()))

    positions = [p for p in positions if p >= 0]

    if positions:
        pos = min(positions)
        start = max(0, pos - 400)
        end = min(len(page_text), pos + 1000)
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
