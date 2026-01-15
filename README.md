# aukcion — мониторинг лотов torgi.gov.ru + Telegram + веб-интерфейс

Приложение:
- мониторит появление новых лотов и изменения статуса на `torgi.gov.ru`
- сохраняет данные в локальную SQLite БД
- отправляет уведомления в Telegram
- даёт веб-интерфейс для задания фильтров и экспорта в Excel

## Установка и запуск (Ubuntu сервер, доступ из интернета) — рекомендуемый вариант

### 1) Клонирование репозитория

```bash
git clone https://github.com/alexkiyashko/aukcion.git
cd aukcion
```

### 2) Настройка Telegram (обязательно)

Откройте `config.py` и укажите:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

```bash
nano config.py
```

### 3) Запуск полного деплоя одним скриптом

Скрипт сам:
- обновит систему
- поставит пакеты (Python, Nginx, Certbot, UFW и т.д.)
- создаст пользователя `torgi`, установит приложение в `/opt/torgi-monitor`
- создаст и запустит `systemd`-службу
- настроит Nginx reverse-proxy
- откроет порты 22/80/443
- (опционально) получит SSL через Let’s Encrypt
- (опционально) настроит ежедневный бэкап БД

```bash
sudo bash deploy.sh
```

В конце скрипт подскажет IP сервера и адрес, по которому будет доступен веб-интерфейс.

### 4) Настройка DNS (субдомен)

В DNS-панели (например DNSFree) создайте **A-запись**:
- имя: `torgi` (или другое)
- значение: публичный IP вашего сервера

После того как DNS “протухнет” (обычно 5–30 минут), сайт будет открываться по вашему домену.

### 5) Проверка статуса

```bash
sudo systemctl status torgi-monitor
sudo journalctl -u torgi-monitor -f
```

## Локальный запуск (для проверки/разработки)

```bash
git clone https://github.com/alexkiyashko/aukcion.git
cd aukcion

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 main.py
```

Веб-интерфейс: `http://localhost:5000`

## Как пользоваться

1. Откройте веб-интерфейс.
2. Задайте фильтры и сохраните.
3. Нажмите “Тестовая проверка” (если есть) или дождитесь авто-проверки (каждые 30 минут).
4. Новые лоты/изменения статуса придут в Telegram.

## Полезные команды (сервер)

```bash
sudo systemctl restart torgi-monitor
sudo systemctl stop torgi-monitor
sudo journalctl -u torgi-monitor -n 200 --no-pager
sudo nginx -t
```

