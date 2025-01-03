import os
import logging
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackContext,
)
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Храним настройки пользователей:
# user_alerts[chat_id] = {
#     "pump_percent": <float>,
#     "time_window": <int>
# }
user_alerts = {}

# ====== Получаем исторические данные с Binance Futures ======

def fetch_historical_price(symbol: str, interval: str, lookback: int):
    """
    Получает исторические данные свечей для заданного символа.
    :param symbol: Торговая пара, например, 'BTCUSDT'
    :param interval: Интервал свечи, например, '1m' для 1 минуты
    :param lookback: Количество свечей для получения
    :return: Список свечей или пустой список в случае ошибки
    """
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": lookback
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        return data  # Список свечей
    except Exception as e:
        logging.error(f"Ошибка при запросе к Binance для {symbol}: {e}")
        return []

def get_price_change_percent(symbol: str, time_window: int):
    """
    Рассчитывает процент изменения цены за заданный временной промежуток.
    :param symbol: Торговая пара, например, 'BTCUSDT'
    :param time_window: Временной промежуток в минутах
    :return: Процент изменения цены или None в случае ошибки
    """
    # Binance поддерживает интервалы до 1 минут
    interval = '1m'
    lookback = time_window + 1  # +1 для получения начальной и конечной цены

    klines = fetch_historical_price(symbol, interval, lookback)
    if len(klines) < lookback:
        logging.warning(f"Недостаточно данных для {symbol}")
        return None

    try:
        start_price = float(klines[0][1])  # Цена открытия первой свечи
        end_price = float(klines[-1][4])   # Цена закрытия последней свечи
        change_percent = ((end_price - start_price) / start_price) * 100
        return change_percent
    except Exception as e:
        logging.error(f"Ошибка при расчёте изменения цены для {symbol}: {e}")
        return None

def check_pump_for_user(chat_id, context: CallbackContext):
    """
    Проверяет, какие монеты выросли на нужный процент за заданный временной промежуток.
    """
    settings = user_alerts.get(chat_id)
    if not settings:
        return  # У пользователя не задано ничего

    pump_percent = settings["pump_percent"]
    time_window = settings["time_window"]  # В минутах

    # Получаем данные о фьючерсных парах
    # Для примера используем список популярных пар
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT']  # Можно расширить список

    pumped_coins = []
    for symbol in symbols:
        change = get_price_change_percent(symbol, time_window)
        if change is None:
            continue
        if change >= pump_percent:
            pumped_coins.append(f"{symbol} ({change:.2f}%)")

    # Если что-то нашли, отправим пользователю
    if pumped_coins:
        message = (
            f"За последние {time_window} минут следующие пары выросли более чем на {pump_percent}%:\n"
            + ", ".join(pumped_coins)
        )
        context.bot.send_message(chat_id=chat_id, text=message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start
    """
    await update.message.reply_text("Привет! Я бот, который ищет пампы на Binance Futures.\n"
                                   "Используй /setalert <процент> <минуты>, чтобы задать условия сканирования.")

async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /setalert <pump_percent> <time_window>
    Например: /setalert 5 15 (отслеживать памп 5% за 15 минут).
    """
    chat_id = update.effective_chat.id
    args = context.args

    if len(args) < 2:
        await update.message.reply_text("Формат: /setalert <процент> <минуты>\n"
                                        "Например: /setalert 5 15")
        return

    try:
        pump_percent = float(args[0])
        time_window = int(args[1])
    except ValueError:
        await update.message.reply_text("Нужно вводить числа, например: /setalert 5 15")
        return

    # Ограничения
    if not (1 <= pump_percent <= 100):
        await update.message.reply_text("Процент должен быть в диапазоне от 1 до 100.")
        return

    if not (1 <= time_window <= 30):
        await update.message.reply_text("Минуты должны быть в диапазоне от 1 до 30.")
        return

    # Сохраняем настройки
    user_alerts[chat_id] = {
        "pump_percent": pump_percent,
        "time_window": time_window
    }

    await update.message.reply_text(
        f"Настройки сохранены.\n"
        f"Буду проверять каждые 1 минуту, есть ли монеты с ростом >= {pump_percent}% за {time_window} мин."
    )

def pump_scanner(context: CallbackContext):
    """
    Функция, которую будет вызывать job_queue каждую минуту.
    Проходимся по всем пользователям, у кого есть настройки, и проверяем памп.
    """
    # Смотрим все chat_id, для которых есть настройки
    for chat_id in user_alerts.keys():
        check_pump_for_user(chat_id, context)

def main():
    # Получаем токен из переменной окружения
    token = os.environ.get("BOT_TOKEN", "NoTokenFound")
    if token == "NoTokenFound":
        logging.error("BOT_TOKEN не установлен в переменных окружения.")
        return

    # Создаём приложение бота
    app = ApplicationBuilder().token(token).build()

    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setalert", set_alert))

    # Запускаем задачу сканирования каждую минуту
    # first=10 означает, что первая проверка произойдёт через 10 секунд после старта
    app.job_queue.run_repeating(pump_scanner, interval=60, first=10)

    # Запускаем бота
    app.run_polling()

if __name__ == "__main__":
    main()
