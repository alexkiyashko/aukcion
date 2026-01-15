# Модуль для работы с Telegram ботом
import requests
from typing import Dict, Optional
import config

class TelegramBot:
    def __init__(self, token: str = config.TELEGRAM_BOT_TOKEN, chat_id: str = config.TELEGRAM_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Отправить сообщение в Telegram"""
        try:
            url = f"{self.api_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return True
            
        except Exception as e:
            print(f"Ошибка при отправке сообщения в Telegram: {e}")
            return False
    
    def format_lot_message(self, lot_data: Dict, is_new: bool = True, old_status: Optional[str] = None) -> str:
        """Форматировать сообщение о лоте для Telegram"""
        if is_new:
            header = "🎯 <b>Новый лот</b>"
        else:
            header = f"🔄 <b>Изменение статуса</b>\nСтарый статус: {old_status or 'Неизвестно'}"
        
        title = lot_data.get('title', 'Без названия')
        lot_number = lot_data.get('lot_number', 'Не указан')
        lot_type = lot_data.get('lot_type', 'Не указан')
        region = lot_data.get('region', 'Не указан')
        address = lot_data.get('address', 'Не указан')
        
        initial_price = lot_data.get('initial_price')
        initial_price_str = f"{initial_price:,.0f} ₽" if initial_price else "—"
        
        current_price = lot_data.get('current_price')
        current_price_str = f"{current_price:,.0f} ₽" if current_price else "—"
        
        deadline = lot_data.get('application_deadline', 'Не указана')
        status = lot_data.get('status', 'Не указан')
        organizer = lot_data.get('organizer', 'Не указан')
        lot_url = lot_data.get('lot_url', '')
        
        message = f"""{header}

<b>Название:</b> {title}
<b>Номер:</b> {lot_number}
<b>Вид торгов:</b> {lot_type}
<b>Регион:</b> {region}
<b>Адрес:</b> {address}
<b>Начальная цена:</b> {initial_price_str}
<b>Текущая цена:</b> {current_price_str}
<b>Подача заявок до:</b> {deadline}
<b>Статус:</b> {status}
<b>Организатор:</b> {organizer}
"""
        
        if lot_url:
            message += f"\n<a href='{lot_url}'>Ссылка на лот</a>"
        
        return message
    
    def notify_new_lot(self, lot_data: Dict) -> bool:
        """Уведомить о новом лоте"""
        message = self.format_lot_message(lot_data, is_new=True)
        return self.send_message(message)
    
    def notify_status_change(self, lot_data: Dict, old_status: str) -> bool:
        """Уведомить об изменении статуса"""
        message = self.format_lot_message(lot_data, is_new=False, old_status=old_status)
        return self.send_message(message)
