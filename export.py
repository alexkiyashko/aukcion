# Модуль для экспорта данных в Excel
import pandas as pd
from datetime import datetime
from typing import List, Dict
import os

def export_to_excel(lots: List[Dict], filename: str = None) -> str:
    """Экспортировать лоты в Excel файл"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"auctions_export_{timestamp}.xlsx"
    
    # Подготовка данных для экспорта
    data = []
    for lot in lots:
        data.append({
            'Номер лота': lot.get('lot_number', ''),
            'Название': lot.get('title', ''),
            'Вид торгов': lot.get('lot_type', ''),
            'Начальная цена': lot.get('initial_price', ''),
            'Текущая цена': lot.get('current_price', ''),
            'Валюта': lot.get('currency', '₽'),
            'Регион': lot.get('region', ''),
            'Адрес': lot.get('address', ''),
            'Дата окончания подачи заявок': lot.get('application_deadline', ''),
            'Статус': lot.get('status', ''),
            'Организатор': lot.get('organizer', ''),
            'Ссылка на лот': lot.get('lot_url', ''),
            'Дата создания': lot.get('created_at', ''),
            'Дата обновления': lot.get('updated_at', '')
        })
    
    # Создание DataFrame
    df = pd.DataFrame(data)
    
    # Экспорт в Excel
    df.to_excel(filename, index=False, engine='openpyxl')
    
    return filename
