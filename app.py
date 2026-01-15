# Веб-приложение Flask
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from datetime import datetime
import os
import database
import parser
import telegram_bot
import config
from export import export_to_excel

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Кастомный фильтр для форматирования чисел
@app.template_filter('format_number')
def format_number(value):
    """Форматирование числа с пробелами в качестве разделителей тысяч"""
    if value is None:
        return '—'
    try:
        return f"{float(value):,.0f}".replace(',', ' ')
    except:
        return str(value)

db = database.Database()
torgi_parser = parser.TorgiParser()
telegram = telegram_bot.TelegramBot()

# Список регионов (можно расширить)
REGIONS = [
    "Алтайский край", "Амурская область", "Архангельская область",
    "Астраханская область", "Белгородская область", "Брянская область",
    "Владимирская область", "Волгоградская область", "Вологодская область",
    "Воронежская область", "Еврейская автономная область", "Забайкальский край",
    "Ивановская область", "Иркутская область", "Кабардино-Балкарская Республика",
    "Калининградская область", "Калужская область", "Камчатский край",
    "Карачаево-Черкесская Республика", "Кемеровская область", "Кировская область",
    "Костромская область", "Краснодарский край", "Красноярский край",
    "Курганская область", "Курская область", "Ленинградская область",
    "Липецкая область", "Магаданская область", "Московская область",
    "Мурманская область", "Ненецкий автономный округ", "Нижегородская область",
    "Новгородская область", "Новосибирская область", "Омская область",
    "Оренбургская область", "Орловская область", "Пензенская область",
    "Пермский край", "Приморский край", "Псковская область",
    "Республика Адыгея", "Республика Алтай", "Республика Башкортостан",
    "Республика Бурятия", "Республика Дагестан", "Республика Ингушетия",
    "Республика Калмыкия", "Республика Карелия", "Республика Коми",
    "Республика Крым", "Республика Марий Эл", "Республика Мордовия",
    "Республика Саха (Якутия)", "Республика Северная Осетия - Алания",
    "Республика Татарстан", "Республика Тыва", "Республика Хакасия",
    "Ростовская область", "Рязанская область", "Самарская область",
    "Саратовская область", "Сахалинская область", "Свердловская область",
    "Севастополь", "Смоленская область", "Ставропольский край",
    "Тамбовская область", "Тверская область", "Томская область",
    "Тульская область", "Тюменская область", "Удмуртская Республика",
    "Ульяновская область", "Хабаровский край", "Ханты-Мансийский автономный округ - Югра",
    "Челябинская область", "Чеченская Республика", "Чувашская Республика",
    "Чукотский автономный округ", "Ямало-Ненецкий автономный округ", "Ярославская область",
    "Москва", "Санкт-Петербург"
]

STATUSES = [
    "Прием заявок",
    "Публикация",
    "Аукцион проведен",
    "Отменен",
    "Закрыт"
]

LOT_TYPES = [
    "Электронный аукцион",
    "Открытый аукцион",
    "Публичное предложение",
    "Конкурс"
]

@app.route('/')
def index():
    """Главная страница с настройкой фильтров"""
    saved_filters = db.get_filters() or {}
    return render_template('index.html', 
                         regions=REGIONS,
                         statuses=STATUSES,
                         lot_types=LOT_TYPES,
                         saved_filters=saved_filters)

@app.route('/api/filters', methods=['POST'])
def save_filters():
    """Сохранить фильтры"""
    try:
        filters = request.json
        db.save_filters(filters)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/filters', methods=['GET'])
def get_filters():
    """Получить сохраненные фильтры"""
    filters = db.get_filters()
    return jsonify(filters or {})

@app.route('/lots')
def lots():
    """Страница со списком лотов"""
    region_filter = request.args.get('region', '')
    status_filter = request.args.get('status', '')
    
    filters = {}
    if region_filter:
        filters['region'] = region_filter
    if status_filter:
        filters['status'] = status_filter
    
    lots_list = db.get_all_lots(filters)
    return render_template('lots.html', lots=lots_list, regions=REGIONS, statuses=STATUSES)

@app.route('/api/lots')
def api_lots():
    """API для получения лотов"""
    region_filter = request.args.get('region', '')
    status_filter = request.args.get('status', '')
    
    filters = {}
    if region_filter:
        filters['region'] = region_filter
    if status_filter:
        filters['status'] = status_filter
    
    lots_list = db.get_all_lots(filters)
    return jsonify(lots_list)

@app.route('/export')
def export():
    """Экспорт лотов в Excel"""
    try:
        region_filter = request.args.get('region', '')
        status_filter = request.args.get('status', '')
        
        filters = {}
        if region_filter:
            filters['region'] = region_filter
        if status_filter:
            filters['status'] = status_filter
        
        lots_list = db.get_all_lots(filters)
        
        filename = export_to_excel(lots_list)
        return send_file(filename, as_attachment=True, download_name=f'auctions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/check', methods=['POST'])
def manual_check():
    """Ручная проверка новых лотов"""
    try:
        filters = db.get_filters() or {}
        lots = torgi_parser.get_all_lots(filters, max_pages=5)
        
        new_count = 0
        updated_count = 0
        
        for lot in lots:
            # Получаем детали лота
            if lot.get('lot_url'):
                try:
                    details = torgi_parser.get_lot_details(lot['lot_url'])
                    lot.update(details)
                except Exception as e:
                    print(f"Не удалось получить детали лота {lot.get('lot_number')}: {e}")
            
            existing_lot = db.get_lot(lot.get('lot_number', ''))
            is_new = db.save_lot(lot)
            
            if is_new:
                new_count += 1
                telegram.notify_new_lot(lot)
            elif existing_lot and existing_lot.get('status') != lot.get('status'):
                updated_count += 1
                telegram.notify_status_change(lot, existing_lot.get('status'))
        
        return jsonify({
            'success': True,
            'new_lots': new_count,
            'updated_lots': updated_count,
            'total_found': len(lots)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/status')
def status():
    """Страница статуса приложения"""
    total_lots = len(db.get_all_lots())
    saved_filters = db.get_filters() or {}
    return render_template('status.html', 
                         total_lots=total_lots,
                         filters=saved_filters,
                         check_interval=config.CHECK_INTERVAL_MINUTES)

if __name__ == '__main__':
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=True)
