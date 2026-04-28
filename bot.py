import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ НОВЫЙ КОД ЗАПУЩЕН\n\n"
        "Это версия MESH_ONLY_TEST.\n"
        "ОК МЦКО здесь больше нет."
    )

async def sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 Проверяю только Портфолио МЭШ:\n\n"
        "https://school.mos.ru/portfolio/student/study\n\n"
        "Версия: MESH_ONLY_TEST"
    )

async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Версия: MESH_ONLY_TEST")

def main():
    app = Application.builder().token(TG_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sites", sites))
    app.add_handler(CommandHandler("version", version))

    print("✅ ЗАПУЩЕН НОВЫЙ КОД MESH_ONLY_TEST")
    app.run_polling()

if __name__ == "__main__":
    main()
