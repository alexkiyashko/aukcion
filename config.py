# Конфигурация приложения
import os

# Telegram Bot настройки
TELEGRAM_BOT_TOKEN = "7217279059:AAHSBLtk3TEsh1VcYb5P-OdemznF-jCnU0Q"
TELEGRAM_CHAT_ID = "7217279059"

# Настройки веб-сервера
# Для разработки используйте "0.0.0.0"
# Для продакшена (за nginx) используйте "127.0.0.1"
WEB_PORT = 5000
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")  # Можно переопределить через переменную окружения

# Настройки базы данных
DATABASE_PATH = "auctions.db"

# Настройки проверки
CHECK_INTERVAL_MINUTES = 30

# URL сайта
TORGI_BASE_URL = "https://torgi.gov.ru/new/public/lots/reg"
