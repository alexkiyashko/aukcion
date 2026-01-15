# Модуль для парсинга сайта torgi.gov.ru
import requests
from bs4 import BeautifulSoup
import re
import json
from typing import List, Dict, Optional
from urllib.parse import urlencode, urljoin
import time
import config

class TorgiParser:
    def __init__(self):
        self.base_url = config.TORGI_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def parse_price(self, price_text: str) -> Optional[float]:
        """Парсинг цены из текста"""
        if not price_text:
            return None
        
        # Удаляем все символы кроме цифр, точек и запятых
        price_clean = re.sub(r'[^\d,.]', '', price_text.replace(' ', ''))
        price_clean = price_clean.replace(',', '.')
        
        try:
            return float(price_clean)
        except:
            return None
    
    def parse_lot_from_row(self, row) -> Optional[Dict]:
        """Парсинг данных одного лота из строки таблицы"""
        try:
            cells = row.find_all('td')
            if len(cells) < 5:
                return None
            
            # Извлекаем ссылку на лот
            link_elem = row.find('a', href=True)
            lot_url = ''
            lot_number = ''
            
            if link_elem:
                lot_url = urljoin(self.base_url, link_elem['href'])
                # Извлекаем номер лота из URL или текста
                lot_number_match = re.search(r'(\d+)', lot_url)
                if lot_number_match:
                    lot_number = lot_number_match.group(1)
            
            # Название лота
            title = ''
            if link_elem:
                title = link_elem.get_text(strip=True)
            
            # Парсим остальные данные из ячеек
            lot_data = {
                'lot_number': lot_number or title[:50],  # Используем название как fallback
                'title': title,
                'lot_url': lot_url,
                'lot_type': '',
                'initial_price': None,
                'current_price': None,
                'currency': '₽',
                'region': '',
                'address': '',
                'application_deadline': '',
                'status': '',
                'organizer': ''
            }
            
            # Пытаемся извлечь данные из ячеек
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                
                # Регион обычно в одной из первых ячеек
                if i < 3 and not lot_data['region']:
                    if any(keyword in text.lower() for keyword in ['край', 'область', 'республика', 'округ']):
                        lot_data['region'] = text
                
                # Цены
                if '₽' in text or 'руб' in text.lower():
                    price = self.parse_price(text)
                    if price and not lot_data['initial_price']:
                        lot_data['initial_price'] = price
                    elif price:
                        lot_data['current_price'] = price
                
                # Даты
                date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', text)
                if date_match and not lot_data['application_deadline']:
                    lot_data['application_deadline'] = date_match.group(0)
                
                # Статус
                status_keywords = ['прием', 'заявок', 'публикация', 'закрыт', 'отменен', 'проведен']
                if any(keyword in text.lower() for keyword in status_keywords):
                    lot_data['status'] = text
            
            return lot_data
            
        except Exception as e:
            print(f"Ошибка при парсинге лота: {e}")
            return None
    
    def get_lots_from_page(self, filters: Dict, page: int = 1) -> List[Dict]:
        """Получить лоты со страницы с применением фильтров"""
        lots = []
        
        try:
            # Пытаемся найти API endpoint для получения данных
            # Многие современные сайты используют API для загрузки данных
            api_url = "https://torgi.gov.ru/new/api/public/lots/search"
            
            # Формируем параметры запроса для API
            api_params = {
                'page': page,
                'size': 20
            }
            
            # Добавляем фильтры
            if filters.get('region'):
                api_params['region'] = filters['region']
            if filters.get('status'):
                api_params['status'] = filters['status']
            if filters.get('lot_type'):
                api_params['lotType'] = filters['lot_type']
            if filters.get('organizer'):
                api_params['organizer'] = filters['organizer']
            if filters.get('min_price'):
                api_params['minPrice'] = filters['min_price']
            if filters.get('max_price'):
                api_params['maxPrice'] = filters['max_price']
            
            # Пытаемся получить данные через API
            try:
                response = self.session.get(api_url, params=api_params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and 'content' in data:
                        # Обрабатываем данные из API
                        for item in data.get('content', []):
                            lot_data = self.parse_lot_from_api(item)
                            if lot_data:
                                lots.append(lot_data)
                        return lots
            except:
                pass  # Если API не работает, переходим к парсингу HTML
            
            # Если API не работает, парсим HTML
            # Формируем параметры запроса для HTML
            params = {}
            
            if filters.get('region'):
                params['region'] = filters['region']
            if filters.get('status'):
                params['status'] = filters['status']
            if filters.get('lot_type'):
                params['lot_type'] = filters['lot_type']
            if filters.get('organizer'):
                params['organizer'] = filters['organizer']
            
            if page > 1:
                params['page'] = page
            
            # Делаем запрос
            url = self.base_url
            if params:
                url += '?' + urlencode(params)
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Ищем различные структуры данных
            # 1. Таблица
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')[1:]  # Пропускаем заголовок
                for row in rows:
                    lot_data = self.parse_lot_from_row(row)
                    if lot_data:
                        lots.append(lot_data)
                return lots
            
            # 2. Список карточек/блоков
            cards = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'lot|card|item|row', re.I))
            if cards:
                for card in cards:
                    lot_data = self.parse_lot_from_card(card)
                    if lot_data:
                        lots.append(lot_data)
                return lots
            
            # 3. JSON данные в script тегах
            scripts = soup.find_all('script', type='application/json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            lot_data = self.parse_lot_from_dict(item)
                            if lot_data:
                                lots.append(lot_data)
                        return lots
                except:
                    continue
            
            # Fallback: если это SPA и данные подгружаются через JS, пробуем headless-браузер (Selenium)
            print("Данные не найдены в HTML/API. Пробуем Selenium (headless)...")
            try:
                lots = self.get_lots_via_selenium(filters=filters, page=page)
                if lots:
                    return lots
            except Exception as e:
                print(f"Selenium fallback failed: {e}")
            
        except Exception as e:
            print(f"Ошибка при получении лотов: {e}")
        
        return lots
    
    def get_all_lots(self, filters: Dict, max_pages: int = 10) -> List[Dict]:
        """Получить все лоты с учетом фильтров (несколько страниц)"""
        all_lots = []
        
        for page in range(1, max_pages + 1):
            print(f"Парсинг страницы {page}...")
            lots = self.get_lots_from_page(filters, page)
            
            if not lots:
                break
            
            all_lots.extend(lots)
            time.sleep(1)  # Небольшая задержка между запросами
        
        return all_lots
    
    def get_lot_details(self, lot_url: str) -> Dict:
        """Получить детальную информацию о лоте"""
        try:
            response = self.session.get(lot_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            details = {}
            
            # Ищем детальную информацию на странице лота
            # Структура может быть разной, поэтому ищем по ключевым словам
            
            # Ищем все элементы с данными
            info_blocks = soup.find_all(['div', 'span', 'p'], class_=re.compile(r'info|data|field|value'))
            
            for block in info_blocks:
                text = block.get_text(strip=True)
                
                # Организатор
                if 'организатор' in text.lower() and not details.get('organizer'):
                    details['organizer'] = text.replace('Организатор', '').strip()
                
                # Адрес
                if 'адрес' in text.lower() and not details.get('address'):
                    details['address'] = text.replace('Адрес', '').strip()
                
                # Регион
                if any(keyword in text.lower() for keyword in ['край', 'область', 'республика']) and not details.get('region'):
                    details['region'] = text.strip()
            
            return details
            
        except Exception as e:
            print(f"Ошибка при получении деталей лота: {e}")
            return {}
    
    def parse_lot_from_api(self, item: Dict) -> Optional[Dict]:
        """Парсинг лота из API ответа"""
        try:
            lot_data = {
                'lot_number': str(item.get('id', item.get('number', ''))),
                'title': item.get('title', item.get('name', '')),
                'lot_type': item.get('lotType', item.get('type', '')),
                'initial_price': item.get('initialPrice', item.get('startPrice')),
                'current_price': item.get('currentPrice', item.get('price')),
                'currency': item.get('currency', '₽'),
                'region': item.get('region', item.get('regionName', '')),
                'address': item.get('address', item.get('location', '')),
                'application_deadline': item.get('applicationDeadline', item.get('deadline', '')),
                'status': item.get('status', item.get('statusName', '')),
                'organizer': item.get('organizer', item.get('organizerName', '')),
                'lot_url': item.get('url', item.get('link', ''))
            }
            
            # Если URL относительный, делаем его абсолютным
            if lot_data['lot_url'] and not lot_data['lot_url'].startswith('http'):
                lot_data['lot_url'] = urljoin(self.base_url, lot_data['lot_url'])
            
            return lot_data
        except Exception as e:
            print(f"Ошибка при парсинге лота из API: {e}")
            return None
    
    def parse_lot_from_card(self, card) -> Optional[Dict]:
        """Парсинг лота из карточки/блока"""
        try:
            lot_data = {
                'lot_number': '',
                'title': '',
                'lot_url': '',
                'lot_type': '',
                'initial_price': None,
                'current_price': None,
                'currency': '₽',
                'region': '',
                'address': '',
                'application_deadline': '',
                'status': '',
                'organizer': ''
            }
            
            # Ищем ссылку
            link = card.find('a', href=True)
            if link:
                lot_data['lot_url'] = urljoin(self.base_url, link['href'])
                lot_data['title'] = link.get_text(strip=True)
                # Извлекаем номер из URL
                lot_number_match = re.search(r'(\d+)', lot_data['lot_url'])
                if lot_number_match:
                    lot_data['lot_number'] = lot_number_match.group(1)
            
            # Ищем все текстовые элементы
            text_elements = card.find_all(['span', 'div', 'p', 'td'])
            for elem in text_elements:
                text = elem.get_text(strip=True)
                
                # Цены
                if '₽' in text or 'руб' in text.lower():
                    price = self.parse_price(text)
                    if price:
                        if not lot_data['initial_price']:
                            lot_data['initial_price'] = price
                        else:
                            lot_data['current_price'] = price
                
                # Регион
                if any(keyword in text.lower() for keyword in ['край', 'область', 'республика', 'округ']):
                    if not lot_data['region']:
                        lot_data['region'] = text
                
                # Статус
                status_keywords = ['прием', 'заявок', 'публикация', 'закрыт', 'отменен', 'проведен']
                if any(keyword in text.lower() for keyword in status_keywords):
                    if not lot_data['status']:
                        lot_data['status'] = text
                
                # Даты
                date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', text)
                if date_match and not lot_data['application_deadline']:
                    lot_data['application_deadline'] = date_match.group(0)
            
            if lot_data['lot_number'] or lot_data['title']:
                return lot_data
            return None
            
        except Exception as e:
            print(f"Ошибка при парсинге карточки: {e}")
            return None
    
    def parse_lot_from_dict(self, item: Dict) -> Optional[Dict]:
        """Парсинг лота из словаря (JSON данных)"""
        return self.parse_lot_from_api(item)


    def get_lots_via_selenium(self, filters: Dict, page: int = 1, wait_seconds: int = 20) -> List[Dict]:
        """Получить лоты через headless Selenium (fallback для SPA)."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
        except Exception as e:
            raise RuntimeError(
                "Selenium не установлен. Установите: pip install -r requirements.txt и пакеты chromium/chromedriver"
            ) from e

        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1920,1080')

        driver = webdriver.Chrome(options=opts)
        try:
            # Для SPA: открываем страницу реестра лотов
            url = self.base_url
            driver.get(url)

            # Ждём появления ссылок на лоты
            wait = WebDriverWait(driver, wait_seconds)
            wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, 'a[href*="/new/public/lots/lot/"]')) > 0)

            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/new/public/lots/lot/"]')
            lots: List[Dict] = []
            seen = set()

            for a in links:
                href = a.get_attribute('href') or ''
                title = (a.text or '').strip()
                if not href or href in seen:
                    continue
                seen.add(href)

                # Номер лота (эвристика из URL)
                lot_number = ''
                m = re.search(r'(\d{6,})', href)
                if m:
                    lot_number = m.group(1)
                else:
                    lot_number = (title[:50] if title else href)

                # Текст контейнера карточки
                container_text = ''
                try:
                    container_text = a.find_element(By.XPATH, 'ancestor::*[self::article or self::li or self::div][1]').text
                except Exception:
                    container_text = title

                lot_data = {
                    'lot_number': lot_number,
                    'title': title or lot_number,
                    'lot_url': href,
                    'lot_type': '',
                    'initial_price': None,
                    'current_price': None,
                    'currency': '₽',
                    'region': '',
                    'address': '',
                    'application_deadline': '',
                    'status': '',
                    'organizer': ''
                }

                # Цены (эвристика)
                prices = re.findall(r'([0-9][0-9\s\u00A0]{2,})\s*₽', container_text)
                if prices:
                    p1 = self.parse_price(prices[0])
                    if p1:
                        lot_data['initial_price'] = p1
                    if len(prices) > 1:
                        p2 = self.parse_price(prices[1])
                        if p2:
                            lot_data['current_price'] = p2

                # Дата (dd.mm.yyyy)
                dm = re.search(r'\b(\d{2}\.\d{2}\.\d{4})\b', container_text)
                if dm:
                    lot_data['application_deadline'] = dm.group(1)

                # Регион/статус (по строкам)
                for line in container_text.split('\n'):
                    low = line.lower()
                    if not lot_data['region'] and any(k in low for k in ['край', 'область', 'республика', 'округ']):
                        lot_data['region'] = line.strip()
                    if not lot_data['status'] and any(k in low for k in ['прием', 'заявок', 'публикац', 'закрыт', 'отменен', 'проведен']):
                        lot_data['status'] = line.strip()

                lots.append(lot_data)

            return lots
        finally:
            driver.quit()
