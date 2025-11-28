import math
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlsplit
from sqlalchemy import or_
from yookassa import Configuration, Payment

from fastapi import Request, UploadFile
from fastapi.templating import Jinja2Templates

from .config import (
    ALLOWED_IMAGE_EXT,
    APP_BASE_URL,
    BASE_DIR,
    MAX_UPLOAD_SIZE,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_DEBUG,
    SMTP_SSL,
    SMTP_USER,
    YOOKASSA_RETURN_URL,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_SHOP_ID,
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def flash(request: Request, category: str, message: str) -> None:
    messages = request.session.get("_messages", [])
    messages.append((category, message))
    request.session["_messages"] = messages


def consume_flash(request: Request):
    return request.session.pop("_messages", [])


async def render(request: Request, template_name: str, context: dict):
    context.setdefault("messages", consume_flash(request))
    context.setdefault("csrf_token", get_csrf_token(request))
    return templates.TemplateResponse(template_name, context)


def get_csrf_token(request: Request) -> str:
    token = request.session.get("_csrf")
    if not token:
        token = secrets.token_hex(16)
        request.session["_csrf"] = token
    return token


def verify_csrf(request: Request, form: dict) -> bool:
    session_token = request.session.get("_csrf")
    form_token = form.get("_csrf")
    return bool(session_token and form_token and session_token == form_token)


def ensure_csrf(request: Request, form: dict) -> bool:
    if verify_csrf(request, form):
        return True
    flash(request, "error", "Некорректный CSRF-токен. Обновите страницу и попробуйте снова.")
    return False


def parse_images(raw: str) -> List[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def save_uploads(files: List[UploadFile]) -> List[str]:
    saved_urls: List[str] = []
    upload_dir = BASE_DIR / "static" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    for file in files:
        if not file or not file.filename:
            continue
        ext = (Path(file.filename).suffix or "").lower()
        if ext and ext not in ALLOWED_IMAGE_EXT:
            continue
        content = file.file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            continue
        name = f"{secrets.token_hex(8)}{ext}"
        dest = upload_dir / name
        dest.write_bytes(content)
        saved_urls.append(f"/static/uploads/{name}")
    return saved_urls


def parse_int_field(value: str, default: int = 0) -> int:
    try:
        value_str = str(value).strip()
        if not value_str:
            return default
        return int(value_str)
    except (ValueError, TypeError):
        return default


def parse_datetime_local(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_form_data(form) -> dict:
    data: dict = {}
    uploads: dict = {}
    for key, value in form.multi_items():
        if isinstance(value, UploadFile):
            uploads.setdefault(key, []).append(value)
        else:
            data[key] = value
    data.update(uploads)
    return data


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def send_email_debug(subject: str, recipient: str, body: str) -> None:
    print(f"EMAIL TO {recipient} | {subject}\n{body}\n")


def send_email(subject: str, recipient: str, body: str) -> bool:
    if not recipient:
        return False
    if not SMTP_HOST or not SMTP_FROM:
        send_email_debug(subject, recipient, body)
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = recipient
        msg.set_content(body)

        use_ssl = SMTP_SSL or SMTP_PORT == 465
        if use_ssl:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT or 465, timeout=10) as server:
                server.set_debuglevel(1 if SMTP_DEBUG else 0)
                if SMTP_USER:
                    server.login(SMTP_USER, SMTP_PASSWORD or "")
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT or 25, timeout=10) as server:
                server.set_debuglevel(1 if SMTP_DEBUG else 0)
                if SMTP_USER:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASSWORD or "")
                server.send_message(msg)
        return True
    except Exception as exc:
        print(f"EMAIL SEND ERROR: {exc}")
        send_email_debug(subject, recipient, body)
        return False


def build_absolute_url(request: Request, route_name: str, **params) -> str:
    raw = str(request.url_for(route_name, **params))
    if APP_BASE_URL:
        path = urlsplit(raw).path or "/"
        return urljoin(APP_BASE_URL.rstrip("/") + "/", path.lstrip("/"))
    return raw


def create_payment_invoice(amount_rub: int, description: str, return_url: str, metadata: dict, customer_email: Optional[str] = None) -> Optional[Tuple[str, str]]:
    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY):
        raise ValueError("YOOKASSA_SHOP_ID или YOOKASSA_SECRET_KEY не заданы")
    if amount_rub <= 0:
        raise ValueError("Сумма платежа должна быть больше нуля")
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY
    idempotence_key = secrets.token_hex(16)
    payload = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "capture": True,
        "description": description[:127],
        "confirmation": {"type": "redirect", "return_url": return_url},
        "metadata": metadata or {},
    }
    if customer_email:
        payload["receipt"] = {
            "customer": {"email": customer_email},
            "items": [
                {
                    "description": description[:128],
                    "quantity": "1.00",
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "vat_code": 1,  # без НДС
                    "payment_subject": "service",
                    "payment_mode": "full_payment",
                }
            ],
        }
    payment = Payment.create(payload, idempotence_key)
    confirmation_url = getattr(getattr(payment, "confirmation", None), "confirmation_url", None)
    if not confirmation_url:
        return None
    return payment.id, confirmation_url


def fetch_payment_status(payment_id: str) -> Optional[str]:
    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY) or not payment_id:
        return None
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY
    payment = Payment.find_one(payment_id)
    return getattr(payment, "status", None)


def get_cart(request: Request) -> List[dict]:
    data = request.session.get("cart", [])
    if isinstance(data, dict):
        migrated = []
        for item_id, qty in data.items():
            migrated.append({"item_id": int(item_id), "start_at": "", "end_at": "", "qty": qty})
        request.session["cart"] = migrated
        return migrated
    if not isinstance(data, list):
        return []
    return data


def save_cart(request: Request, cart: List[dict]):
    request.session["cart"] = cart


def calculate_rental_price(item, start_at: str, end_at: str, qty: int = 1) -> Tuple[int, datetime, datetime, str]:
    start_dt = parse_datetime_local(start_at) or datetime.utcnow()
    end_dt = parse_datetime_local(end_at)
    if not end_dt or end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)
    hours = max(1, math.ceil((end_dt - start_dt).total_seconds() / 3600))
    days = math.ceil(hours / 24)

    def pick_hour_tariff():
        if item.price_per_hour:
            return (hours * item.price_per_hour, "от часа")
        return None

    def pick_three_hour_tariff():
        if item.price_per_3h:
            return (hours * item.price_per_3h, "от 3 часов")
        return None

    def pick_day_tariff(label: str = "от дня"):
        if item.price_per_day:
            return (days * item.price_per_day, label)
        return None

    def pick_week_tariff():
        if item.price_per_week:
            return (days * item.price_per_week, "от недели")
        return None

    offer = None
    if hours < 3:
        offer = pick_hour_tariff() or pick_three_hour_tariff() or pick_day_tariff() or pick_week_tariff()
    elif hours < 24:
        offer = pick_three_hour_tariff() or pick_hour_tariff() or pick_day_tariff() or pick_week_tariff()
    elif hours < 24 * 7:
        offer = pick_day_tariff() or pick_week_tariff() or pick_three_hour_tariff() or pick_hour_tariff()
    else:
        offer = pick_week_tariff() or pick_day_tariff(label="от дня (неделя)") or pick_three_hour_tariff() or pick_hour_tariff()

    if not offer:
        offer = (0, "")

    qty_safe = max(1, qty)
    price, tariff_label = offer
    price *= qty_safe
    return price, start_dt, end_dt, tariff_label


def intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start


def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_cart_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    return parse_datetime_local(value)


def check_item_availability(item_id: int, start_dt: datetime, end_dt: datetime, db, cart: List[dict], skip_cart_idx: Optional[int] = None) -> Optional[str]:
    from .models import Order

    active_orders = (
        db.query(Order)
        .filter(
            Order.item_id == item_id,
            Order.start_at.isnot(None),
            Order.end_at.isnot(None),
            or_(Order.payment_status.is_(None), Order.payment_status != 'canceled'),
        )
        .all()
    )
    for order in active_orders:
        o_start = parse_cart_dt(order.start_at)
        o_end = parse_cart_dt(order.end_at)
        if not o_start or not o_end:
            continue
        if intervals_overlap(start_dt, end_dt, o_start, o_end):
            return f"Этот товар уже занят другим пользователем: {format_dt(o_start)} — {format_dt(o_end)}."

    for idx, entry in enumerate(cart):
        if skip_cart_idx is not None and idx == skip_cart_idx:
            continue
        if int(entry.get("item_id", 0)) != item_id:
            continue
        e_start = parse_cart_dt(entry.get("start_at", ""))
        e_end = parse_cart_dt(entry.get("end_at", ""))
        if not e_start or not e_end:
            continue
        if intervals_overlap(start_dt, end_dt, e_start, e_end):
            return f"Вы уже выбрали этот товар: {format_dt(e_start)} — {format_dt(e_end)}."

    return None


def get_current_user(request: Request, db):
    from .models import User

    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id)).first()
