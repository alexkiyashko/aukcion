#!/bin/bash
# Универсальный скрипт развертывания Torgi Monitor на Ubuntu
# Выполняет все действия от обновления сервера до запуска приложения

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция вывода сообщений
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    error "Запустите скрипт с правами sudo: sudo bash deploy.sh"
    exit 1
fi

echo "=========================================="
echo "  Развертывание Torgi Monitor"
echo "  Универсальный скрипт установки"
echo "=========================================="
echo ""

# Переменные
APP_DIR="/opt/torgi-monitor"
APP_USER="torgi"
DOMAIN=""
EMAIL=""
CURRENT_DIR=$(pwd)

# Запрос данных
echo "Введите данные для развертывания:"
read -p "Доменное имя (например: torgi.example.com): " DOMAIN
read -p "Email для Let's Encrypt: " EMAIL
read -p "Настроить автоматическое резервное копирование? (y/n): " SETUP_BACKUP

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    error "Доменное имя и email обязательны"
    exit 1
fi

# Извлечение имени субдомена
SUBDOMAIN=$(echo "$DOMAIN" | cut -d'.' -f1)

echo ""
info "Начинаем развертывание для домена: $DOMAIN"
echo ""

# ==========================================
# ШАГ 1: Обновление системы
# ==========================================
info "[1/12] Обновление системы..."
apt update -qq
apt upgrade -y -qq
success "Система обновлена"

# ==========================================
# ШАГ 2: Установка необходимых пакетов
# ==========================================
info "[2/12] Установка пакетов..."
apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx ufw curl > /dev/null 2>&1
success "Пакеты установлены"

# ==========================================
# ШАГ 3: Создание пользователя
# ==========================================
info "[3/12] Создание пользователя $APP_USER..."
if ! id "$APP_USER" &>/dev/null; then
    adduser --system --group --home "$APP_DIR" --no-create-home "$APP_USER"
    success "Пользователь $APP_USER создан"
else
    warning "Пользователь $APP_USER уже существует"
fi

# ==========================================
# ШАГ 4: Создание директории приложения
# ==========================================
info "[4/12] Создание директории приложения..."
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
success "Директория создана: $APP_DIR"

# ==========================================
# ШАГ 5: Копирование файлов приложения
# ==========================================
info "[5/12] Копирование файлов приложения..."

# Проверка наличия основных файлов
if [ ! -f "$CURRENT_DIR/main.py" ]; then
    error "Файлы приложения не найдены в текущей директории: $CURRENT_DIR"
    error "Убедитесь, что вы запускаете скрипт из корня проекта"
    exit 1
fi

# Копирование файлов (исключая ненужные)
rsync -av --exclude='venv' \
         --exclude='__pycache__' \
         --exclude='*.pyc' \
         --exclude='.git' \
         --exclude='*.db' \
         --exclude='*.xlsx' \
         --exclude='test_*.py' \
         --exclude='deploy.sh' \
         "$CURRENT_DIR/" "$APP_DIR/"

chown -R "$APP_USER:$APP_USER" "$APP_DIR"
success "Файлы скопированы"

# ==========================================
# ШАГ 6: Установка зависимостей Python
# ==========================================
info "[6/12] Установка зависимостей Python..."
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
success "Зависимости установлены"

# ==========================================
# ШАГ 7: Настройка конфигурации
# ==========================================
info "[7/12] Настройка конфигурации..."
sed -i 's/WEB_HOST = .*/WEB_HOST = "127.0.0.1"/' "$APP_DIR/config.py"
success "Конфигурация обновлена (WEB_HOST = 127.0.0.1)"

# ==========================================
# ШАГ 8: Создание systemd службы
# ==========================================
info "[8/12] Создание systemd службы..."
cat > /etc/systemd/system/torgi-monitor.service <<EOF
[Unit]
Description=Torgi.gov.ru Auction Monitor
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable torgi-monitor > /dev/null 2>&1
success "Systemd служба создана и включена"

# ==========================================
# ШАГ 9: Настройка Nginx
# ==========================================
info "[9/12] Настройка Nginx..."

# Создание конфигурации Nginx
cat > /etc/nginx/sites-available/torgi-monitor <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

# Активация конфигурации
ln -sf /etc/nginx/sites-available/torgi-monitor /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Проверка конфигурации
if nginx -t > /dev/null 2>&1; then
    systemctl reload nginx
    success "Nginx настроен и перезагружен"
else
    error "Ошибка в конфигурации Nginx"
    nginx -t
    exit 1
fi

# ==========================================
# ШАГ 10: Настройка файрвола
# ==========================================
info "[10/12] Настройка файрвола..."
ufw allow 22/tcp > /dev/null 2>&1
ufw allow 80/tcp > /dev/null 2>&1
ufw allow 443/tcp > /dev/null 2>&1
ufw --force enable > /dev/null 2>&1
success "Файрвол настроен (порты 22, 80, 443 открыты)"

# ==========================================
# ШАГ 11: Получение SSL сертификата
# ==========================================
info "[11/12] Получение SSL сертификата..."
info "Проверьте, что DNS запись для $DOMAIN указывает на этот сервер"
read -p "Продолжить получение SSL? (y/n): " CONTINUE_SSL

if [ "$CONTINUE_SSL" = "y" ] || [ "$CONTINUE_SSL" = "Y" ]; then
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$EMAIL" --redirect; then
        success "SSL сертификат получен и настроен"
    else
        warning "Не удалось получить SSL сертификат. Проверьте DNS записи."
        warning "Вы можете получить сертификат позже командой:"
        warning "sudo certbot --nginx -d $DOMAIN"
    fi
else
    warning "Получение SSL пропущено. Выполните позже:"
    warning "sudo certbot --nginx -d $DOMAIN"
fi

# ==========================================
# ШАГ 12: Запуск службы
# ==========================================
info "[12/12] Запуск службы приложения..."
systemctl start torgi-monitor
sleep 3

if systemctl is-active --quiet torgi-monitor; then
    success "Служба запущена успешно"
else
    error "Ошибка при запуске службы"
    systemctl status torgi-monitor --no-pager
    exit 1
fi

# ==========================================
# ДОПОЛНИТЕЛЬНО: Настройка резервного копирования
# ==========================================
if [ "$SETUP_BACKUP" = "y" ] || [ "$SETUP_BACKUP" = "Y" ]; then
    info "Настройка автоматического резервного копирования..."
    
    # Создание скрипта бэкапа
    cat > "$APP_DIR/backup.sh" <<'BACKUP_SCRIPT'
#!/bin/bash
BACKUP_DIR="/opt/backups/torgi-monitor"
APP_DIR="/opt/torgi-monitor"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

if [ -f "$APP_DIR/auctions.db" ]; then
    cp "$APP_DIR/auctions.db" "$BACKUP_DIR/auctions_$DATE.db"
    find "$BACKUP_DIR" -name "auctions_*.db" -mtime +7 -exec gzip {} \;
    find "$BACKUP_DIR" -name "auctions_*.db.gz" -mtime +30 -delete
    echo "Backup completed: $DATE"
else
    echo "Error: Database file not found"
    exit 1
fi
BACKUP_SCRIPT

    chmod +x "$APP_DIR/backup.sh"
    chown "$APP_USER:$APP_USER" "$APP_DIR/backup.sh"
    
    # Добавление в crontab (каждый день в 3:00)
    (crontab -u "$APP_USER" -l 2>/dev/null; echo "0 3 * * * $APP_DIR/backup.sh") | crontab -u "$APP_USER" -
    
    success "Автоматическое резервное копирование настроено (каждый день в 3:00)"
fi

# ==========================================
# ИТОГОВАЯ ИНФОРМАЦИЯ
# ==========================================
echo ""
echo "=========================================="
success "Развертывание завершено успешно!"
echo "=========================================="
echo ""
echo "Приложение доступно по адресу:"
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "  https://$DOMAIN"
else
    echo "  http://$DOMAIN (SSL не настроен)"
fi
echo ""
echo "Полезные команды:"
echo "  sudo systemctl status torgi-monitor    - статус службы"
echo "  sudo journalctl -u torgi-monitor -f    - просмотр логов"
echo "  sudo systemctl restart torgi-monitor   - перезапуск"
echo "  sudo systemctl stop torgi-monitor       - остановка"
echo ""
echo "Настройка DNS:"
echo "  Добавьте A-запись в DNSFree:"
echo "    Имя: $SUBDOMAIN"
echo "    Тип: A"
echo "    Значение: $(curl -s ifconfig.me)"
echo ""
echo "Если DNS еще не настроен, приложение будет доступно"
echo "после настройки DNS и получения SSL сертификата."
echo ""
