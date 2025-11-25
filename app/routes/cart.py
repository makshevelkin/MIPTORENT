from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Item, Order
from ..utils import (
    calculate_rental_price,
    check_item_availability,
    flash,
    get_cart,
    get_current_user,
    parse_datetime_local,
    parse_form_data,
    render,
    save_cart,
)

router = APIRouter()


@router.post("/cart/add/{item_id}")
async def cart_add(request: Request, item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        flash(request, "error", "Товар не найден.")
        return RedirectResponse(url=request.url_for("index"), status_code=303)
    form_raw = await request.form()
    form = parse_form_data(form_raw)
    from ..utils import ensure_csrf

    if not ensure_csrf(request, form):
        return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)

    start_at = form.get("start_at", "").strip()
    end_at = form.get("end_at", "").strip()
    qty_raw = form.get("qty", "1")
    try:
        qty = max(1, int(qty_raw))
    except (TypeError, ValueError):
        qty = 1
    start_dt = parse_datetime_local(start_at)
    end_dt = parse_datetime_local(end_at)
    if not start_dt or not end_dt:
        flash(request, "error", "Укажите корректные даты и время.")
        return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)
    if end_dt <= start_dt:
        flash(request, "error", "Окончание не может быть раньше или равно началу.")
        return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)
    cart = get_cart(request)
    if isinstance(cart, dict):
        cart = []
    conflict = check_item_availability(item.id, start_dt, end_dt, db, cart)
    if conflict:
        flash(request, "error", conflict)
        return RedirectResponse(url=request.url_for("item_detail", item_id=item.id), status_code=303)
    cart.append(
        {
            "item_id": item.id,
            "start_at": start_dt.strftime("%Y-%m-%d %H:%M"),
            "end_at": end_dt.strftime("%Y-%m-%d %H:%M"),
            "qty": qty,
        }
    )
    save_cart(request, cart)
    flash(request, "success", "Товар добавлен в корзину.")
    return RedirectResponse(url=request.url_for("cart"), status_code=303)


@router.post("/cart/remove/{item_id}")
async def cart_remove(request: Request, item_id: int):
    cart = get_cart(request)
    if not isinstance(cart, list):
        cart = []
    form_raw = await request.form()
    form = parse_form_data(form_raw)
    from ..utils import ensure_csrf

    if not ensure_csrf(request, form):
        return RedirectResponse(url=request.url_for("cart"), status_code=303)
    try:
        entry_idx = int(form.get("entry_idx", -1))
    except (TypeError, ValueError):
        entry_idx = -1
    if 0 <= entry_idx < len(cart) and cart[entry_idx].get("item_id") == item_id:
        cart.pop(entry_idx)
        flash(request, "success", "Строка удалена из корзины.")
    else:
        flash(request, "error", "Не удалось удалить строку.")
    save_cart(request, cart)
    return RedirectResponse(url=request.url_for("cart"), status_code=303)


@router.post("/checkout")
async def checkout(request: Request, db: Session = Depends(get_db)):
    form_raw = await request.form()
    form = parse_form_data(form_raw)
    from ..utils import ensure_csrf

    if not ensure_csrf(request, form):
        return RedirectResponse(url=request.url_for("cart"), status_code=303)
    cart = get_cart(request)
    if not cart:
        flash(request, "error", "Корзина пуста.")
        return RedirectResponse(url=request.url_for("cart"), status_code=303)
    user = get_current_user(request, db)
    if not user:
        flash(request, "error", "Авторизуйтесь, чтобы оформить оплату.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    item_ids = [entry.get("item_id") for entry in cart if entry.get("item_id")]
    items = {item.id: item for item in db.query(Item).filter(Item.id.in_(item_ids)).all()}
    total = 0
    for idx, entry in enumerate(cart):
        item = items.get(entry.get("item_id"))
        if not item:
            continue
        qty_raw = entry.get("qty", 1)
        try:
            qty = max(1, int(qty_raw))
        except (TypeError, ValueError):
            qty = 1
        start_at = entry.get("start_at") or ""
        end_at = entry.get("end_at") or ""
        start_dt = parse_datetime_local(start_at)
        end_dt = parse_datetime_local(end_at)
        if not start_dt or not end_dt or end_dt <= start_dt:
            flash(request, "error", "В корзине есть позиция с некорректными датами. Исправьте и попробуйте снова.")
            return RedirectResponse(url=request.url_for("cart"), status_code=303)
        conflict = check_item_availability(item.id, start_dt, end_dt, db, cart, skip_cart_idx=idx)
        if conflict:
            flash(request, "error", conflict)
            return RedirectResponse(url=request.url_for("cart"), status_code=303)
        line_total, start_dt, end_dt, _ = calculate_rental_price(item, start_at, end_at, qty)
        date_from = start_dt.strftime("%Y-%m-%d")
        date_to = end_dt.strftime("%Y-%m-%d")
        order = Order(
            date_from=date_from,
            date_to=date_to,
            status="оплачено",
            user_id=user.id,
            item_id=item.id,
            start_at=start_dt.strftime("%Y-%m-%d %H:%M"),
            end_at=end_dt.strftime("%Y-%m-%d %H:%M"),
        )
        db.add(order)
        total += line_total
    db.commit()
    save_cart(request, [])
    flash(
        request,
        "success",
        f"Оплата проведена (тест). Созданы заказы со статусом 'оплачено' на сумму {total} ₽ за выбранные периоды. Подключите эквайринг и замените этот шаг.",
    )
    return RedirectResponse(url=request.url_for("cart"), status_code=303)


@router.get("/cart")
async def cart(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    cart_data = get_cart(request)
    if isinstance(cart_data, dict):
        cart_data = []
    items_map = {item.id: item for item in db.query(Item).all()}
    cart_items = []
    total = 0
    cleaned_cart = []
    for entry in cart_data:
        item_id = entry.get("item_id")
        item = items_map.get(item_id)
        if not item:
            continue
        qty_raw = entry.get("qty", 1)
        try:
            qty = max(1, int(qty_raw))
        except (ValueError, TypeError):
            qty = 1
        start_at = entry.get("start_at", "")
        end_at = entry.get("end_at", "")
        line_total, start_dt, end_dt, tariff_label = calculate_rental_price(item, start_at, end_at, qty)
        total += line_total
        normalized_entry = {
            "item_id": item_id,
            "start_at": start_dt.strftime("%Y-%m-%d %H:%M"),
            "end_at": end_dt.strftime("%Y-%m-%d %H:%M"),
            "qty": qty,
            "tariff": tariff_label,
        }
        cleaned_cart.append(normalized_entry)
        cart_items.append(
            {
                "item": item,
                "qty": qty,
                "line_total": line_total,
                "start_at": normalized_entry["start_at"],
                "end_at": normalized_entry["end_at"],
                "tariff": tariff_label,
            }
        )
    save_cart(request, cleaned_cart)
    return await render(
        request,
        "cart.html",
        {"request": request, "current_user": user, "cart_items": cart_items, "total": total},
    )
