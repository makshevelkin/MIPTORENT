from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Item, Order
from ..utils import (
    calculate_rental_price,
    check_item_availability,
    flash,
    get_cart,
    get_current_user,
    parse_datetime_local,
    parse_form_data,
    render,
)

router = APIRouter()


@router.get("/", response_class=RedirectResponse)
async def root_redirect(request: Request):
    return RedirectResponse(url=request.url_for("index"))


@router.get("/catalog", name="index")
async def index(request: Request, q: str = "", category: str = "", db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    q_norm = q.strip().lower()
    categories = db.query(Category).order_by(Category.name).all()
    items_query = db.query(Item)
    if category:
        items_query = items_query.filter(Item.category_id == int(category))
    items = items_query.all()
    if q_norm:
        words = [w for w in q_norm.split() if w]
        filtered = []
        for item in items:
            haystack = " ".join([item.name or "", item.short_description or "", item.description or ""]).lower()
            if all(w in haystack for w in words):
                filtered.append(item)
        items = filtered
    return await render(
        request,
        "index.html",
        {
            "request": request,
            "items": items,
            "q": q_norm,
            "category_id": int(category) if category else None,
            "categories": categories,
            "current_user": user,
        },
    )


@router.api_route("/item/{item_id}", methods=["GET", "POST"])
async def item_detail(request: Request, item_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        return RedirectResponse(url=request.url_for("index"), status_code=302)

    bookings = (
        db.query(Order)
        .filter(
            Order.item_id == item_id,
            Order.start_at.isnot(None),
            Order.end_at.isnot(None),
            Order.status.in_(["в обработке", "подтверждено", "оплачено"]),
        )
        .order_by(Order.start_at)
        .all()
    )

    if request.method == "POST":
        if not user:
            flash(request, "error", "Для бронирования нужно авторизоваться.")
            return RedirectResponse(url=request.url_for("login") + f"?next={request.url.path}", status_code=303)
        if not user.email_confirmed:
            flash(request, "error", "Подтвердите email перед оформлением заказа.")
            return RedirectResponse(url=request.url_for("profile"), status_code=303)

        form_raw = await request.form()
        form = parse_form_data(form_raw)
        start_at = form.get("start_at", "").strip()
        end_at = form.get("end_at", "").strip()
        if not (start_at and end_at):
            flash(request, "error", "Заполните даты и время аренды.")
        else:
            try:
                start_dt = parse_datetime_local(start_at)
                end_dt = parse_datetime_local(end_at)
            except ValueError:
                flash(request, "error", "Неверный формат даты. Используйте выбор в календаре.")
                return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)

            if not start_dt or not end_dt:
                flash(request, "error", "Не удалось распознать даты. Попробуйте ещё раз.")
                return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)

            if end_dt <= start_dt:
                flash(request, "error", "Окончание не может быть раньше или равно началу.")
                return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)

            conflict = check_item_availability(item.id, start_dt, end_dt, db, get_cart(request))
            if conflict:
                flash(request, "error", conflict)
                return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)

            date_from = start_at.split(" ")[0]
            date_to = end_at.split(" ")[0]
            order = Order(
                date_from=date_from,
                date_to=date_to,
                status="в обработке",
                user_id=user.id,
                item_id=item.id,
                start_at=start_at,
                end_at=end_at,
            )
            db.add(order)
            db.commit()
            flash(request, "success", "Бронирование создано.")
            return RedirectResponse(url=request.url_for("profile"), status_code=303)

    return await render(
        request,
        "item.html",
        {"request": request, "item": item, "current_user": user, "bookings": bookings},
    )
