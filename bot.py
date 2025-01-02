import logging
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from binance.client import Client as BinanceClient
from pybit import HTTP
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Получение API-ключей из переменных окружения
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
# BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Инициализация клиентов
binance_client = BinanceClient(BINANCE_API_KEY, BINANCE_API_SECRET)
# bybit_client = HTTP(
#     endpoint="https://api.bybit.com",
#     api_key=BYBIT_API_KEY,
#     api_secret=BYBIT_API_SECRET
# )

# Хранение настроек пользователей
user_settings = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для отслеживания пампов на Binance и ByBit.\n"
        "Используй /setpump <%> <минут> для настройки параметров мониторинга.\n"
        "Например: /setpump 5 10 - отслеживать памп от 5% за 10 минут."
    )

# Команда /setpump
async def setpump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        percent = float(context.args[0])
        minutes = int(context.args[1])
        if not (1 <= percent <= 100) or not (1 <= minutes <= 30):
            raise ValueError
        user_id = update.message.from_user.id
        user_settings[user_id] = {'percent': percent, 'minutes': minutes}
        await update.message.reply_text(
            f"Настройки обновлены: Памп ≥ {percent}% за {minutes} минут."
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Неверный формат. Используй: /setpump <%> <минут>\nНапример: /setpump 5 10"
        )

# Функция для получения цен с Binance
def get_binance_prices():
    prices = binance_client.futures_mark_price()
    return {item['symbol']: float(item['markPrice']) for item in prices}

# Функция для получения цен с ByBit
# def get_bybit_prices():
#     response = bybit_client.latest_information_for_symbol()
#     prices = {}
#     if 'result' in response:
#         for item in response['result']:
#             symbol = item['symbol']
#             last_price = float(item['last_price'])
#             prices[symbol] = last_price
#     return prices

# Хранение истории цен
price_history = {}

# Основная функция мониторинга
async def monitor_pumps(app):
    while True:
        current_time = datetime.utcnow()
        # Получаем цены
        binance_prices = get_binance_prices()
        # bybit_prices = get_bybit_prices()
        # all_prices = {**binance_prices, **bybit_prices}
        all_prices = {**binance_prices}

        # Обновляем историю цен
        for symbol, price in all_prices.items():
            if symbol not in price_history:
                price_history[symbol] = []
            price_history[symbol].append({'time': current_time, 'price': price})
            # Удаляем старые записи (старше 30 минут)
            cutoff = current_time - timedelta(minutes=30)
            price_history[symbol] = [entry for entry in price_history[symbol] if entry['time'] >= cutoff]

        # Проверяем настройки пользователей
        for user_id, settings in user_settings.items():
            percent = settings['percent']
            minutes = settings['minutes']
            cutoff_time = current_time - timedelta(minutes=minutes)
            for symbol, history in price_history.items():
                # Находим цену в начале интервала
                initial_prices = [entry for entry in history if entry['time'] <= cutoff_time]
                if not initial_prices:
                    continue
                initial_price = initial_prices[0]['price']
                current_price = history[-1]['price']
                change = ((current_price - initial_price) / initial_price) * 100
                if change >= percent:
                    # Отправляем уведомление
                    message = (
                        f"🚀 Памп обнаружен!\n"
                        f"Пара: {symbol}\n"
                        f"Изменение: {change:.2f}% за {minutes} минут."
                    )
                    try:
                        await app.bot.send_message(chat_id=user_id, text=message)
                        # Удаляем запись, чтобы избежать повторных уведомлений
                        price_history[symbol] = []
                    except Exception as e:
                        logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

        # Ждем 60 секунд до следующей проверки
        await asyncio.sleep(60)

# Запуск бота
async def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setpump", setpump))

    # Запускаем мониторинг в фоновом режиме
    application.job_queue.run_once(lambda context: asyncio.create_task(monitor_pumps(application)), 0)

    # Запускаем бота
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
