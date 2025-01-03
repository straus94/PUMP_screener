import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello world!")

def main():
    # Считываем токен из переменной окружения, например BOT_TOKEN
    token = os.environ.get("BOT_TOKEN", "NoTokenFound")

    # Если токен не найден — выводим ошибку и завершаем.
    if token == "NoTokenFound":
        logging.error("BOT_TOKEN не установлен в переменных окружения.")
        return

    # Создаём приложение бота
    app = ApplicationBuilder().token(token).build()

    # Регистрируем хендлер для команды /start
    app.add_handler(CommandHandler("start", start))

    # Запускаем бота в режиме polling
    app.run_polling()

if __name__ == "__main__":
    main()


# import platform
# import asyncio

# # 1) Устанавливаем на Windows SelectorEventLoopPolicy до любых других импортов
# if platform.system() == "Windows":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# import logging
# import os
# import sys
# from datetime import datetime, timedelta, timezone

# from telegram import Update
# from telegram.ext import (
#     ApplicationBuilder,
#     CommandHandler,
#     ContextTypes
# )
# from binance.client import Client as BinanceClient
# from dotenv import load_dotenv

# price_history = {}
# user_settings = {}
# binance_client = None

# def check_env():
#     load_dotenv()
#     BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
#     BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
#     TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

#     if not all([BINANCE_API_KEY, BINANCE_API_SECRET, TELEGRAM_TOKEN]):
#         logging.error("Одна или несколько переменных окружения не установлены.")
#         sys.exit(1)

#     return BINANCE_API_KEY, BINANCE_API_SECRET, TELEGRAM_TOKEN


# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "Привет! Я бот для отслеживания пампов на Binance.\n"
#         "Используй /setpump <%> <минут> для настройки параметров мониторинга.\n"
#         "Например: /setpump 5 10 - отслеживать памп от 5% за 10 минут."
#     )


# async def setpump(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         percent = float(context.args[0])
#         minutes = int(context.args[1])
#         if not (1 <= percent <= 100) or not (1 <= minutes <= 30):
#             raise ValueError
#         user_id = update.message.from_user.id
#         user_settings[user_id] = {'percent': percent, 'minutes': minutes}
#         await update.message.reply_text(
#             f"Настройки обновлены: Памп ≥ {percent}% за {minutes} минут."
#         )
#     except (IndexError, ValueError):
#         await update.message.reply_text(
#             "Неверный формат. Используй: /setpump <%> <минут>\nНапример: /setpump 5 10"
#         )


# def get_binance_prices():
#     prices = binance_client.futures_mark_price()
#     return {item['symbol']: float(item['markPrice']) for item in prices}


# async def monitor_pumps(app):
#     while True:
#         current_time = datetime.now(timezone.utc)
#         binance_prices = get_binance_prices()

#         # Обновляем историю цен
#         for symbol, price in binance_prices.items():
#             if symbol not in price_history:
#                 price_history[symbol] = []
#             price_history[symbol].append({'time': current_time, 'price': price})

#             cutoff = current_time - timedelta(minutes=30)
#             price_history[symbol] = [
#                 entry for entry in price_history[symbol]
#                 if entry['time'] >= cutoff
#             ]

#         # Проверяем настройки пользователей
#         for user_id, settings in user_settings.items():
#             percent = settings['percent']
#             minutes = settings['minutes']
#             cutoff_time = current_time - timedelta(minutes=minutes)

#             for symbol, history in price_history.items():
#                 initial_prices = [
#                     entry for entry in history
#                     if entry['time'] <= cutoff_time
#                 ]
#                 if not initial_prices:
#                     continue

#                 initial_price = initial_prices[0]['price']
#                 current_price = history[-1]['price']
#                 change = ((current_price - initial_price) / initial_price) * 100

#                 if change >= percent:
#                     message = (
#                         f"🚀 Памп обнаружен!\n"
#                         f"Пара: {symbol}\n"
#                         f"Изменение: {change:.2f}% за {minutes} мин."
#                     )
#                     try:
#                         await app.bot.send_message(chat_id=user_id, text=message)
#                         price_history[symbol] = []
#                     except Exception as e:
#                         logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

#         await asyncio.sleep(60)


# async def main():
#     BINANCE_API_KEY, BINANCE_API_SECRET, TELEGRAM_TOKEN = check_env()

#     global binance_client
#     binance_client = BinanceClient(BINANCE_API_KEY, BINANCE_API_SECRET)

#     application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

#     application.add_handler(CommandHandler("start", start))
#     application.add_handler(CommandHandler("setpump", setpump))

#     # Запускаем мониторинг в фоне
#     asyncio.create_task(monitor_pumps(application))

#     # Стартуем бота
#     await application.run_polling()


# if __name__ == "__main__":
#     logging.basicConfig(
#         format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#         level=logging.INFO
#     )

#     asyncio.run(main())
