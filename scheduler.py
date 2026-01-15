# Модуль планировщика задач
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import database
import parser
import telegram_bot
import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuctionScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.db = database.Database()
        self.torgi_parser = parser.TorgiParser()
        self.telegram = telegram_bot.TelegramBot()
        self.is_running = False
    
    def check_auctions(self):
        """Проверка новых аукционов и изменений статусов"""
        logger.info("Начало проверки аукционов...")
        
        try:
            # Получаем сохраненные фильтры
            filters = self.db.get_filters() or {}
            
            if not filters:
                logger.warning("Фильтры не настроены, пропуск проверки")
                return
            
            # Получаем лоты с сайта
            lots = self.torgi_parser.get_all_lots(filters, max_pages=5)
            logger.info(f"Найдено {len(lots)} лотов на сайте")
            
            new_count = 0
            updated_count = 0
            
            for lot in lots:
                # Получаем детали лота, если есть URL
                if lot.get('lot_url'):
                    try:
                        details = self.torgi_parser.get_lot_details(lot['lot_url'])
                        lot.update(details)
                    except Exception as e:
                        logger.warning(f"Не удалось получить детали лота {lot.get('lot_number')}: {e}")
                
                # Проверяем, существует ли лот в БД
                existing_lot = self.db.get_lot(lot.get('lot_number', ''))
                
                # Сохраняем лот
                is_new = self.db.save_lot(lot)
                
                if is_new:
                    new_count += 1
                    logger.info(f"Новый лот: {lot.get('title', 'Без названия')}")
                    self.telegram.notify_new_lot(lot)
                elif existing_lot:
                    # Проверяем изменение статуса
                    old_status = existing_lot.get('status', '')
                    new_status = lot.get('status', '')
                    
                    if old_status != new_status:
                        updated_count += 1
                        logger.info(f"Изменение статуса лота {lot.get('lot_number')}: {old_status} -> {new_status}")
                        self.telegram.notify_status_change(lot, old_status)
            
            logger.info(f"Проверка завершена. Новых: {new_count}, Обновлено: {updated_count}")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке аукционов: {e}")
    
    def start(self):
        """Запустить планировщик"""
        if self.is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        # Добавляем задачу проверки каждые 30 минут
        self.scheduler.add_job(
            func=self.check_auctions,
            trigger=IntervalTrigger(minutes=config.CHECK_INTERVAL_MINUTES),
            id='check_auctions',
            name='Проверка новых аукционов',
            replace_existing=True
        )
        
        # Запускаем проверку сразу при старте
        self.check_auctions()
        
        self.scheduler.start()
        self.is_running = True
        logger.info(f"Планировщик запущен. Проверка каждые {config.CHECK_INTERVAL_MINUTES} минут")
    
    def stop(self):
        """Остановить планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Планировщик остановлен")
