from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Item, ItemImage, Order
from ..utils import (
    flash,
    get_cart,
    get_current_user,
    parse_form_data,
    parse_images,
    parse_int_field,
    render,
    save_uploads,
    ensure_csrf,
)

router = APIRouter()


def require_admin(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user or user.role != "admin":
        return None
    return user


@router.get("/admin/items")
async def admin_items(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    items = db.query(Item).order_by(Item.id.desc()).all()
    categories = db.query(Category).order_by(Category.name).all()
    return await render(
        request,
        "admin_items.html",
        {"request": request, "items": items, "categories": categories, "current_user": admin},
    )


@router.api_route("/admin/items/new", methods=["GET", "POST"])
async def admin_item_new(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    categories = db.query(Category).order_by(Category.name).all()
    if request.method == "POST":
        form_raw = await request.form()
        form = parse_form_data(form_raw)
        if not ensure_csrf(request, form):
            return RedirectResponse(url=request.url_for("admin_item_new"), status_code=303)
        name = form.get("name", "").strip()
        price_per_hour = parse_int_field(form.get("price_per_hour", "0"))
        price_per_3h = parse_int_field(form.get("price_per_3h", "0"))
        price_per_day = parse_int_field(form.get("price_per_day", "0"))
        price_per_week = parse_int_field(form.get("price_per_week", "0"))
        short_description = form.get("short_description", "").strip()
        description = form.get("description", "").strip()
        category_id = form.get("category_id", "").strip()
        images_raw = form.get("images", "")
        image_files = form.get("image_files", [])
        if not isinstance(image_files, list):
            image_files = [image_files] if image_files else []

        if not (name and short_description and description and category_id):
            flash(request, "error", "Заполните все поля.")
        elif not any([price_per_hour, price_per_3h, price_per_day, price_per_week]):
            flash(request, "error", "Укажите хотя бы одну цену.")
        else:
            item = Item(
                name=name,
                price_per_hour=price_per_hour,
                price_per_3h=price_per_3h,
                price_per_day=price_per_day,
                price_per_week=price_per_week,
                short_description=short_description,
                description=description,
                category_id=int(category_id),
            )
            db.add(item)
            db.flush()

            urls = parse_images(images_raw) + save_uploads(image_files)
            for url in urls:
                db.add(ItemImage(url=url, item=item))

            db.commit()
            flash(request, "success", "Товар создан.")
            return RedirectResponse(url=request.url_for("admin_items"), status_code=303)

    return await render(
        request,
        "admin_item_form.html",
        {
            "request": request,
            "item": None,
            "categories": categories,
            "current_user": admin,
            "images_text": "",
        },
    )


@router.api_route("/admin/items/{item_id}/edit", methods=["GET", "POST"])
async def admin_item_edit(request: Request, item_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        flash(request, "error", "Товар не найден.")
        return RedirectResponse(url=request.url_for("admin_items"), status_code=303)

    categories = db.query(Category).order_by(Category.name).all()

    if request.method == "POST":
        form_raw = await request.form()
        form = parse_form_data(form_raw)
        if not ensure_csrf(request, form):
            return RedirectResponse(url=request.url_for("admin_item_edit", item_id=item_id), status_code=303)
        name = form.get("name", "").strip()
        price_per_hour = parse_int_field(form.get("price_per_hour", "0"))
        price_per_3h = parse_int_field(form.get("price_per_3h", "0"))
        price_per_day = parse_int_field(form.get("price_per_day", "0"))
        price_per_week = parse_int_field(form.get("price_per_week", "0"))
        short_description = form.get("short_description", "").strip()
        description = form.get("description", "").strip()
        category_id = form.get("category_id", "").strip()
        images_raw = form.get("images", "")
        image_files = form.get("image_files", [])
        if not isinstance(image_files, list):
            image_files = [image_files] if image_files else []

        if not (name and short_description and description and category_id):
            flash(request, "error", "Заполните все поля.")
        elif not any([price_per_hour, price_per_3h, price_per_day, price_per_week]):
            flash(request, "error", "Укажите хотя бы одну цену.")
        else:
            item.name = name
            item.price_per_hour = price_per_hour
            item.price_per_3h = price_per_3h
            item.price_per_day = price_per_day
            item.price_per_week = price_per_week
            item.short_description = short_description
            item.description = description
            item.category_id = int(category_id)

            db.query(ItemImage).filter(ItemImage.item_id == item.id).delete()
            urls = parse_images(images_raw) + save_uploads(image_files)
            for url in urls:
                db.add(ItemImage(url=url, item=item))

            db.commit()
            flash(request, "success", "Товар обновлен.")
            return RedirectResponse(url=request.url_for("admin_items"), status_code=303)

    images_text = "\n".join(img.url for img in item.images) if item.images else ""
    return await render(
        request,
        "admin_item_form.html",
        {
            "request": request,
            "item": item,
            "images_text": images_text,
            "categories": categories,
            "current_user": admin,
        },
    )


@router.post("/admin/items/{item_id}/delete")
async def admin_item_delete(request: Request, item_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    form_raw = await request.form()
    form = parse_form_data(form_raw)
    if not ensure_csrf(request, form):
        return RedirectResponse(url=request.url_for("admin_items"), status_code=303)
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        flash(request, "error", "Товар не найден.")
        return RedirectResponse(url=request.url_for("admin_items"), status_code=303)
    db.query(ItemImage).filter(ItemImage.item_id == item.id).delete()
    db.query(Order).filter(Order.item_id == item.id).delete()
    db.delete(item)
    db.commit()
    flash(request, "success", "Товар удален.")
    return RedirectResponse(url=request.url_for("admin_items"), status_code=303)


@router.get("/admin/categories")
async def admin_categories(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    categories = db.query(Category).order_by(Category.name).all()
    return await render(
        request,
        "admin_categories.html",
        {"request": request, "categories": categories, "current_user": admin},
    )


@router.post("/admin/categories/new")
async def admin_category_new(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    form_raw = await request.form()
    form = parse_form_data(form_raw)
    if not ensure_csrf(request, form):
        return RedirectResponse(url=request.url_for("admin_categories"), status_code=303)
    name = form.get("name", "").strip()
    if not name:
        flash(request, "error", "Название обязательно.")
    elif db.query(Category).filter(Category.name == name).first():
        flash(request, "error", "Такая категория уже есть.")
    else:
        db.add(Category(name=name))
        db.commit()
        flash(request, "success", "Категория добавлена.")
    return RedirectResponse(url=request.url_for("admin_categories"), status_code=303)


@router.post("/admin/categories/{category_id}/edit")
async def admin_category_edit(request: Request, category_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    form_raw = await request.form()
    form = parse_form_data(form_raw)
    if not ensure_csrf(request, form):
        return RedirectResponse(url=request.url_for("admin_categories"), status_code=303)
    name = form.get("name", "").strip()
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        flash(request, "error", "Категория не найдена.")
    elif not name:
        flash(request, "error", "Название обязательно.")
    else:
        category.name = name
        db.commit()
        flash(request, "success", "Категория обновлена.")
    return RedirectResponse(url=request.url_for("admin_categories"), status_code=303)


@router.post("/admin/categories/{category_id}/delete")
async def admin_category_delete(request: Request, category_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        flash(request, "error", "Нужны права администратора.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    form_raw = await request.form()
    form = parse_form_data(form_raw)
    if not ensure_csrf(request, form):
        return RedirectResponse(url=request.url_for("admin_categories"), status_code=303)
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        flash(request, "error", "Категория не найдена.")
    elif db.query(Item).filter(Item.category_id == category.id).first():
        flash(request, "error", "Нельзя удалить категорию с товарами.")
    else:
        db.delete(category)
        db.commit()
        flash(request, "success", "Категория удалена.")
    return RedirectResponse(url=request.url_for("admin_categories"), status_code=303)
