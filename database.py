# Модуль для работы с базой данных
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import config

class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Получить соединение с базой данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализация базы данных - создание таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица для хранения лотов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_number TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                lot_type TEXT,
                initial_price REAL,
                current_price REAL,
                currency TEXT,
                region TEXT,
                address TEXT,
                application_deadline TEXT,
                status TEXT,
                organizer TEXT,
                lot_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для хранения истории изменений статусов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_number TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lot_number) REFERENCES lots(lot_number)
            )
        ''')
        
        # Таблица для хранения фильтров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filter_name TEXT,
                filter_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Индексы для ускорения поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lot_number ON lots(lot_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON lots(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_region ON lots(region)')
        
        conn.commit()
        conn.close()
    
    def save_lot(self, lot_data: Dict) -> bool:
        """Сохранить или обновить лот в базе данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        lot_number = lot_data.get('lot_number', '')
        if not lot_number:
            conn.close()
            return False
        
        # Проверяем, существует ли лот
        cursor.execute('SELECT * FROM lots WHERE lot_number = ?', (lot_number,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующий лот
            old_status = existing['status']
            new_status = lot_data.get('status', '')
            
            # Если статус изменился, сохраняем в историю
            if old_status != new_status:
                cursor.execute('''
                    INSERT INTO status_history (lot_number, old_status, new_status)
                    VALUES (?, ?, ?)
                ''', (lot_number, old_status, new_status))
            
            cursor.execute('''
                UPDATE lots SET
                    title = ?,
                    lot_type = ?,
                    initial_price = ?,
                    current_price = ?,
                    currency = ?,
                    region = ?,
                    address = ?,
                    application_deadline = ?,
                    status = ?,
                    organizer = ?,
                    lot_url = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE lot_number = ?
            ''', (
                lot_data.get('title', ''),
                lot_data.get('lot_type', ''),
                lot_data.get('initial_price'),
                lot_data.get('current_price'),
                lot_data.get('currency', ''),
                lot_data.get('region', ''),
                lot_data.get('address', ''),
                lot_data.get('application_deadline', ''),
                lot_data.get('status', ''),
                lot_data.get('organizer', ''),
                lot_data.get('lot_url', ''),
                lot_number
            ))
            is_new = False
        else:
            # Вставляем новый лот
            cursor.execute('''
                INSERT INTO lots (
                    lot_number, title, lot_type, initial_price, current_price,
                    currency, region, address, application_deadline, status,
                    organizer, lot_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                lot_number,
                lot_data.get('title', ''),
                lot_data.get('lot_type', ''),
                lot_data.get('initial_price'),
                lot_data.get('current_price'),
                lot_data.get('currency', ''),
                lot_data.get('region', ''),
                lot_data.get('address', ''),
                lot_data.get('application_deadline', ''),
                lot_data.get('status', ''),
                lot_data.get('organizer', ''),
                lot_data.get('lot_url', '')
            ))
            is_new = True
        
        conn.commit()
        conn.close()
        return is_new
    
    def get_lot(self, lot_number: str) -> Optional[Dict]:
        """Получить лот по номеру"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM lots WHERE lot_number = ?', (lot_number,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_lots(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Получить все лоты с опциональными фильтрами"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM lots WHERE 1=1'
        params = []
        
        if filters:
            if filters.get('region'):
                query += ' AND region LIKE ?'
                params.append(f"%{filters['region']}%")
            if filters.get('status'):
                query += ' AND status = ?'
                params.append(filters['status'])
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def save_filters(self, filters: Dict):
        """Сохранить фильтры"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Удаляем старые фильтры (оставляем только последние)
        cursor.execute('DELETE FROM filters')
        
        # Сохраняем новые
        cursor.execute('''
            INSERT INTO filters (filter_name, filter_data)
            VALUES (?, ?)
        ''', ('last_filters', json.dumps(filters, ensure_ascii=False)))
        
        conn.commit()
        conn.close()
    
    def get_filters(self) -> Optional[Dict]:
        """Получить сохраненные фильтры"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT filter_data FROM filters ORDER BY updated_at DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row['filter_data'])
        return None
    
    def get_status_changes(self, lot_number: str) -> List[Dict]:
        """Получить историю изменений статуса для лота"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM status_history
            WHERE lot_number = ?
            ORDER BY changed_at DESC
        ''', (lot_number,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
