from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user")
    email_confirmed = Column(Boolean, nullable=False, default=False)
    confirmation_token = Column(String(255), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)

    orders = relationship("Order", backref="user", lazy="joined")

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)


class Category(Base):
    __tablename__ = "category"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)

    items = relationship("Item", backref="category", lazy="joined")


class Item(Base):
    __tablename__ = "item"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    price_per_hour = Column(Integer, nullable=False, default=0)
    price_per_3h = Column(Integer, nullable=False, default=0)
    price_per_day = Column(Integer, nullable=False, default=0)
    price_per_week = Column(Integer, nullable=False, default=0)
    short_description = Column(Text, nullable=False)
    description = Column(Text, nullable=False)

    category_id = Column(Integer, ForeignKey("category.id"), nullable=False)
    images = relationship("ItemImage", backref="item", lazy="joined")
    orders = relationship("Order", backref="item", lazy="joined")


class ItemImage(Base):
    __tablename__ = "item_image"

    id = Column(Integer, primary_key=True)
    url = Column(String(500), nullable=False)
    item_id = Column(Integer, ForeignKey("item.id"), nullable=False)


class Order(Base):
    __tablename__ = "order"

    id = Column(Integer, primary_key=True)
    date_from = Column(String(10), nullable=False)
    date_to = Column(String(10), nullable=False)
    status = Column(String(80), nullable=False, default="в обработке")
    start_at = Column(String(19), nullable=True)
    end_at = Column(String(19), nullable=True)

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("item.id"), nullable=False)
