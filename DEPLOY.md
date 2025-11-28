Инструкция по деплою проекта MIPTORENT

Документ описывает полный процесс развёртывания и обновления проекта на сервере Ubuntu 22.04.

1. Структура проекта на сервере

Проект размещён по пути:

/var/www/MIPTORENT/

Структура:

MIPTORENT/
├── app/
├── static/
├── templates/
├── rental.db
├── seed.py
├── .env
├── venv/
├── deploy.sh
├── requirements.txt
├── README.md
└── ...

Системные файлы:

/etc/systemd/system/miptorent.service
/etc/nginx/sites-enabled/miptorent.conf

2. Файлы, которые не должны попадать в Git
rental.db
.env
venv/
__pycache__/
deploy.sh
miptorent.service

3. Деплой новых обновлений

Основной процесс:

sudo bash /var/www/MIPTORENT/deploy.sh

Скрипт выполняет:

Остановку сервиса

Получение обновлений из Git

Установку зависимостей

Автоматическую фиксацию прав

Применение миграций SQLite

Перезапуск FastAPI

Проверку статуса

4. Автоматическая фиксация прав

После обновления репозитория необходимо, чтобы проект принадлежал пользователю:

www-data:www-data

Авто-фиксация выполняется:

sudo chown -R www-data:www-data /var/www/MIPTORENT
sudo find /var/www/MIPTORENT -type d -exec chmod 775 {} \;
sudo find /var/www/MIPTORENT -type f -exec chmod 664 {} \;
sudo chmod 664 /var/www/MIPTORENT/rental.db

5. Миграции SQLite

Миграции выполняются через скрипт:

from app.seed import migrate; migrate()

Ручной запуск:

source venv/bin/activate
python3 -c "from app.seed import migrate; migrate()"

6. Управление сервисом FastAPI
sudo systemctl start miptorent
sudo systemctl stop miptorent
sudo systemctl restart miptorent
sudo systemctl status miptorent

7. Проверка работы приложения
curl -I http://127.0.0.1:8000/

8. Просмотр логов
sudo journalctl -u miptorent -n 100 --no-pager

9. Работа с Nginx

Проверить корректность конфигурации:

sudo nginx -t

Если ошибок нет:

sudo systemctl reload nginx

10. Обновление Python-зависимостей
source venv/bin/activate
pip install -r requirements.txt

11. Пересоздание виртуального окружения (если требуется)
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

12. Проверка базы данных

Проверить путь и права:

ls -l /var/www/MIPTORENT/rental.db

При необходимости:

sudo chmod 664 rental.db
sudo chown www-data:www-data rental.db

13. Полный ручной деплой (если без deploy.sh)
cd /var/www/MIPTORENT
sudo systemctl stop miptorent
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo chown -R www-data:www-data /var/www/MIPTORENT
python3 -c "from app.seed import migrate; migrate()"
sudo systemctl restart miptorent
sudo systemctl status miptorent

14. Проверка домена и SSL
sudo nginx -t
sudo systemctl reload nginx
curl -I https://miptorent.ru

15. Перезагрузка сервера (при необходимости)
sudo reboot

Конец документа
