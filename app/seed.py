from datetime import datetime, timedelta

from sqlalchemy import or_, text

from .database import SessionLocal, engine
from .models import Base, Category, Item, ItemImage, Order, User


def ensure_schema(db):
    columns = {row[1] for row in db.execute(text("PRAGMA table_info(user)"))}
    alters = []
    if "role" not in columns:
        alters.append("ALTER TABLE user ADD COLUMN role TEXT DEFAULT 'user'")
    if "email_confirmed" not in columns:
        alters.append("ALTER TABLE user ADD COLUMN email_confirmed BOOLEAN DEFAULT 0")
    if "confirmation_token" not in columns:
        alters.append("ALTER TABLE user ADD COLUMN confirmation_token TEXT")
    if "reset_token" not in columns:
        alters.append("ALTER TABLE user ADD COLUMN reset_token TEXT")
    if "reset_token_expires_at" not in columns:
        alters.append("ALTER TABLE user ADD COLUMN reset_token_expires_at DATETIME")
    for statement in alters:
        db.execute(text(statement))
    if alters:
        db.commit()
    db.execute(text("UPDATE user SET role='user' WHERE role IS NULL"))
    db.execute(text("UPDATE user SET email_confirmed=0 WHERE email_confirmed IS NULL"))
    db.commit()

    order_columns = {row[1] for row in db.execute(text("PRAGMA table_info(`order`)"))}
    order_alters = []
    if "start_at" not in order_columns:
        order_alters.append("ALTER TABLE `order` ADD COLUMN start_at TEXT")
    if "end_at" not in order_columns:
        order_alters.append("ALTER TABLE `order` ADD COLUMN end_at TEXT")
    if "payment_id" not in order_columns:
        order_alters.append("ALTER TABLE `order` ADD COLUMN payment_id TEXT")
    if "payment_status" not in order_columns:
        order_alters.append("ALTER TABLE `order` ADD COLUMN payment_status TEXT")
    if "status" in order_columns:
        db.execute(text("UPDATE `order` SET status='в обработке' WHERE status='pending'"))
        db.execute(text("UPDATE `order` SET status='подтверждено' WHERE status='confirmed'"))
    for statement in order_alters:
        db.execute(text(statement))
    if order_alters:
        db.commit()

    item_columns = {row[1] for row in db.execute(text("PRAGMA table_info(item)"))}
    item_alters = []
    if "price_per_hour" not in item_columns:
        item_alters.append("ALTER TABLE item ADD COLUMN price_per_hour INTEGER DEFAULT 0")
    if "price_per_3h" not in item_columns:
        item_alters.append("ALTER TABLE item ADD COLUMN price_per_3h INTEGER DEFAULT 0")
    if "price_per_week" not in item_columns:
        item_alters.append("ALTER TABLE item ADD COLUMN price_per_week INTEGER DEFAULT 0")
    for statement in item_alters:
        db.execute(text(statement))
    if item_alters:
        db.commit()


def seed_data(db):
    if not db.query(Category).first():
        tech = Category(name="Электроника")
        clothes = Category(name="Одежда")
        sport = Category(name="Спорттовары")
        tools = Category(name="Инструменты")
        db.add_all([tech, clothes, sport, tools])
        db.flush()

        camera = Item(
            name="Камера Canon EOS",
            price_per_hour=300,
            price_per_3h=250, # 20% дешевле/час, 3 часа
            price_per_day=3000,
            price_per_week=2500, 
            category=tech,
            short_description="Лёгкая зеркалка с китовым объективом, удобно брать в поездки.",
            description="Зеркальная камера Canon EOS 18-55mm. В комплекте аккумулятор и карта 32 ГБ.",
        )
        projector = Item(
            name="Проектор Xiaomi",
            price_per_hour=400,
            price_per_3h=350,
            price_per_day=4000,
            price_per_week=3000,
            category=tech,
            short_description="Компактный проектор с HDMI, выводит Full HD.",
            description="Подходит для домашних киносеансов и презентаций, подключение по HDMI.",
        )
        suit = Item(
            name="Костюм классический (M-L)",
            price_per_hour=150,
            price_per_3h=120,
            price_per_day=1500,
            price_per_week=1200,
            category=clothes,
            short_description="Тёмный костюм slim fit, размер M-L.",
            description="Двухпредметный костюм. Химчистка выполнена, готов к мероприятиям.",
        )
        dumbbells = Item(
            name="Гантели разборные (2×10 кг)",
            price_per_hour=120,
            price_per_3h=100,
            price_per_day=1200,
            price_per_week=1000,
            category=sport,
            short_description="Пара разборных гантелей с шагом 0.5 кг.",
            description="Блины 0.5/1/2.5 кг, фиксаторы в комплекте. Удобно для дома и зала.",
        )
        drill = Item(
            name="Перфоратор Bosch",
            price_per_hour=200,
            price_per_3h=160,
            price_per_day=2000,
            price_per_week=1800,
            category=tools,
            short_description="Перфоратор SDS+ для сверления и долбления.",
            description="Скорость 1100 об/мин, сила удара 2.7 Дж. В комплекте кейс и буры 6/8/10 мм.",
        )
        db.add_all([camera, projector, suit, dumbbells, drill])
        db.flush()

        images = [
            ItemImage(url="https://placehold.co/600x400?text=Camera+1", item=camera),
            ItemImage(url="https://placehold.co/600x400?text=Camera+2", item=camera),
            ItemImage(url="https://placehold.co/600x400?text=Camera+3", item=camera),
            ItemImage(url="https://placehold.co/600x400?text=Projector+1", item=projector),
            ItemImage(url="https://placehold.co/600x400?text=Projector+2", item=projector),
            ItemImage(url="https://placehold.co/600x400?text=Suit+1", item=suit),
            ItemImage(url="https://placehold.co/600x400?text=Dumbbells", item=dumbbells),
            ItemImage(url="https://placehold.co/600x400?text=Drill", item=drill),
        ]
        db.add_all(images)

        demo_user = User(email="user@example.com", full_name="Демо пользователь", role="user", email_confirmed=True)
        demo_user.set_password("test1234")
        db.add(demo_user)
        db.flush()

        order1 = Order(
            date_from="2025-11-25",
            date_to="2025-11-27",
            status="подтверждено",
            user=demo_user,
            item=camera,
            start_at="2025-11-25 10:00",
            end_at="2025-11-27 12:00",
        )
        order2 = Order(
            date_from="2025-12-01",
            date_to="2025-12-02",
            status="в обработке",
            user=demo_user,
            item=suit,
            start_at="2025-12-01 18:00",
            end_at="2025-12-02 10:00",
        )
        db.add_all([order1, order2])
        db.commit()

    admin = db.query(User).filter(User.email == "admin123@example.com").first()
    legacy_admin = db.query(User).filter(User.email == "admin@example.com").first()
    if not admin and legacy_admin:
        legacy_admin.email = "admin123@example.com"
        legacy_admin.full_name = "Администратор"
        legacy_admin.role = "admin"
        legacy_admin.email_confirmed = True
        legacy_admin.set_password("2a6-Nvc-36h-LKc")
        db.commit()
        admin = legacy_admin
    if not admin:
        admin = User(
            email="admin123@example.com",
            full_name="Администратор",
            role="admin",
            email_confirmed=True,
        )
        admin.set_password("2a6-Nvc-36h-LKc")
        db.add(admin)
        db.commit()


def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_schema(db)
        seed_data(db)
