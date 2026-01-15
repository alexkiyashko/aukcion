# Главный файл запуска приложения
import threading
from app import app
import scheduler
import config
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_scheduler():
    """Запустить планировщик в отдельном потоке"""
    auction_scheduler = scheduler.AuctionScheduler()
    auction_scheduler.start()

if __name__ == '__main__':
    logger.info("Запуск приложения мониторинга аукционов...")
    
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Запускаем веб-сервер
    logger.info(f"Веб-сервер запущен на http://{config.WEB_HOST}:{config.WEB_PORT}")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False, use_reloader=False)
