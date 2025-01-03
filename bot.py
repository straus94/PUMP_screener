import os
import logging
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackContext,
    JobQueue,
    Job
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Храним настройки пользователей:
# user_alerts[chat_id] = {
#     "pump_percent": <int>,
#     "time_window": <int>
# }
user_alerts = {}

# ====== Получаем цену (или свечи) с Binance Futures ======

def fetch_futures_prices():
    """
    Получаем данные по всем парам фьючерсов.
    Для примера используем 24h тикеры:
    https://binance-docs.github.io/apidocs/futures/en/#24hr-ticker-price-change-statistics
    Вернёт список словарей, где у каждого тикера есть поля:
      - symbol
      - lastPrice
      - openPrice
      - priceChangePercent (и т.д.)
    """
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        return data  # список словарей
    except Exception as e:
        logging.error(f"Ошибка при запросе к Binance: {e}")
        return []

def check_pump_for_user(chat_id, context: CallbackContext):
    """
    Проверяем, какие монеты выросли на нужный процент за нужный промежуток
    (упрощённо используем priceChangePercent за 24 часа).
    В реальном случае нужно было бы подгрузить исторические данные за N минут.
    """
    # Берём настройки пользователя
    settings = user_alerts.get(chat_id)
    if not settings:
        return  # У пользователя не задано ничего

    pump_percent = settings["pump_percent"]
    time_window = settings["time_window"]  # пока не используем в упрощённом примере

    # Получаем данные о фьючерсных парах
    ticker_data = fetch_futures_prices()
    if not ticker_data:
        return

    # Фильтруем пары, у которых процент роста за 24h >= pump_percent
    pumped_coins = []
    for item in ticker_data:
        try:
            symbol = item["symbol"]
            price_change_pct = float(item["priceChangePercent"])  # 24h процент
            if price_change_pct >= pump_percent:
                pumped_coins.append(symbol)
        except:
            # Если вдруг не хватило полей, пропустим
            continue

    # Если что-то нашли, отправим пользователю
    if pumped_coins:
        message = (
            f"За последние 24 часа эти пары выросли более чем на {pump_percent}%:\n"
            + ", ".join(pumped_coins)
        )
        context.bot.send_message(chat_id=chat_id, text=message)

def pump_scanner(context: CallbackContext):
    """
    Функция, которую будет вызывать job_queue каждую минуту.
    Проходимся по всем пользователям, у кого есть настройки, и проверяем памп.
    """
    # Смотрим все chat_id, для которых есть настройки
    for chat_id in user_alerts.keys():
        check_pump_for_user(chat_id, context)

# ====== Обработчики команд ======

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
