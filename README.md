# MIPTORENT

Сервис аренды техники и снаряжения на FastAPI + SQLite с шаблонами Jinja2, сессионной авторизацией и интеграцией платежей YooKassa.

## Возможности
- Каталог товаров с категориями и поиском по тексту.
- Бронирование с выбором дат/времени, корзина и расчёт тарифов.
- Оформление заказов и проверка статусов оплаты через YooKassa (при наличии ключей).
- Личный кабинет: авторизация, подтверждение e-mail, восстановление пароля, просмотр броней.
- Админ-панель: управление категориями, товарами, изображениями и заказами.
- Простые миграции SQLite и автоправка прав на `rental.db` при инициализации.

## Требования
- Python 3.11+ (рекомендуется)
- SQLite (встроен)
- Git, virtualenv

## Установка и локальный запуск
1) Установить зависимости:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
2) Создать файл `.env` в корне проекта (см. пример ниже).
3) Инициализировать БД и данные:
```bash
python -c "from app.seed import init_db; init_db()"
```
4) Запустить сервер разработки:
```bash
uvicorn app.main:app --reload
```

## Переменные окружения (.env)
- `SESSION_SECRET` — случайная строка для шифрования сессий (обязательна).
- `SESSION_COOKIE_SECURE` — `1` для HTTPS, `0` для http.
- `SESSION_COOKIE_SAMESITE` — `lax`/`strict`.
- `APP_BASE_URL` — базовый URL приложения (нужен для возврата с платежей).
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SSL` (`0/1`), `SMTP_DEBUG` (`0/1`).
- YooKassa: `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `YOOKASSA_RETURN_URL` (по умолчанию `APP_BASE_URL`).

## База данных и миграции
- БД: `rental.db` в корне проекта. При старте `app.main` вызывается `init_db()` из `app/seed.py`, создаёт таблицы, применяет схему, наполняет демоданными и пытается выставить права на файл БД (uid/gid 33 — www-data).
- Дополнительные миграции SQLite:  
  ```bash
  python -c "from app.seed import migrate; migrate()"
  ```

## Тестовые учётные данные
- Админ: `admin123@example.com` / `2a6-Nvc-36h-LKc`
- Пользователь: `user@example.com` / `test1234`

## Структура проекта
- `app/main.py` — точка входа FastAPI.
- `app/routes/` — публичные, аутентификационные, корзина/заказы и админ-маршруты.
- `app/models.py` — модели SQLAlchemy.
- `app/utils.py` — утилиты: CSRF, сессии, платежи, загрузки, расчёт тарифов.
- `app/seed.py` — создание/миграции схемы, демо-данные, фиксация прав.
- `templates/`, `static/` — фронт-шаблоны и статика.

## Деплой
Подробная инструкция: `DEPLOY.md` (systemd + Nginx, deploy.sh, права и миграции).
