from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Item, Order, User
from ..utils import (
    build_absolute_url,
    ensure_csrf,
    flash,
    generate_token,
    get_cart,
    get_current_user,
    parse_form_data,
    render,
    send_email,
)

router = APIRouter()


@router.api_route("/login", methods=["GET", "POST"], response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url=request.url_for("profile"), status_code=302)

    if request.method == "POST":
        form_raw = await request.form()
        form = parse_form_data(form_raw)
        if not ensure_csrf(request, form):
            return RedirectResponse(url=request.url_for("login"), status_code=303)
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        found = db.query(User).filter(User.email == email).first()
        if found and found.check_password(password):
            if not found.email_confirmed:
                if not found.confirmation_token:
                    found.confirmation_token = generate_token()
                    db.commit()
                link = build_absolute_url(request, "confirm_email", token=found.confirmation_token)
                send_email("Подтверждение email", found.email, f"Ссылка: {link}\nКод: {found.confirmation_token}")
                flash(request, "error", "Подтвердите email перед входом. Ссылка отправлена на почту.")
                return RedirectResponse(url=request.url_for("login"), status_code=303)

            request.session["user_id"] = found.id
            flash(request, "success", "Успешный вход.")
            next_url = request.query_params.get("next")
            return RedirectResponse(url=next_url or request.url_for("profile"), status_code=303)
        else:
            flash(request, "error", "Неверные учётные данные.")

    return await render(
        request,
        "login.html",
        {"request": request, "current_user": None},
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user_id", None)
    flash(request, "success", "Вы успешно вышли из аккаунта.")
    return RedirectResponse(url=request.url_for("index"), status_code=303)


@router.api_route("/register", methods=["GET", "POST"], response_class=HTMLResponse)
async def register(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url=request.url_for("profile"), status_code=302)

    if request.method == "POST":
        form_raw = await request.form()
        form = parse_form_data(form_raw)
        if not ensure_csrf(request, form):
            return RedirectResponse(url=request.url_for("register"), status_code=303)
        name = form.get("name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")

        if not (name and email and password):
            flash(request, "error", "Заполните все поля.")
        elif db.query(User).filter(User.email == email).first():
            flash(request, "error", "Пользователь с таким email уже существует.")
        else:
            new_user = User(full_name=name, email=email, role="user")
            new_user.set_password(password)
            new_user.confirmation_token = generate_token()
            db.add(new_user)
            db.commit()
            link = build_absolute_url(request, "confirm_email", token=new_user.confirmation_token)
            sent = send_email(
                "Подтверждение email",
                new_user.email,
                f"Ссылка: {link}\nКод: {new_user.confirmation_token}",
            )
            if sent:
                flash(request, "success", "Регистрация успешна. Проверьте email для подтверждения.")
            else:
                flash(request, "success", f"Регистрация успешна. Письмо не отправилось — используйте ссылку: {link}")
            return RedirectResponse(url=request.url_for("login"), status_code=303)

    return await render(
        request,
        "register.html",
        {"request": request, "current_user": None},
    )


@router.get("/confirm/{token}")
async def confirm_email(request: Request, token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.confirmation_token == token).first()
    if not user:
        flash(request, "error", "Ссылка подтверждения неактуальна.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    user.email_confirmed = True
    user.confirmation_token = None
    db.commit()
    flash(request, "success", "Email подтверждён.")
    return RedirectResponse(url=request.url_for("login"), status_code=303)


@router.api_route("/forgot-password", methods=["GET", "POST"], response_class=HTMLResponse)
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form_raw = await request.form()
        form = parse_form_data(form_raw)
        if not ensure_csrf(request, form):
            return RedirectResponse(url=request.url_for("forgot_password"), status_code=303)
        email = form.get("email", "").strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.reset_token = generate_token()
            user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
            db.commit()
            link = build_absolute_url(request, "reset_password", token=user.reset_token)
            sent = send_email("Сброс пароля", user.email, f"Ссылка для сброса: {link}")
            if sent:
                flash(request, "success", "Ссылка для сброса отправлена на email.")
            else:
                flash(request, "success", f"Ссылка для сброса: {link}")
        else:
            flash(request, "success", "Если email существует, мы отправим инструкцию.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    return await render(
        request,
        "forgot_password.html",
        {"request": request, "current_user": None},
    )


@router.api_route("/reset/{token}", methods=["GET", "POST"], response_class=HTMLResponse)
async def reset_password(request: Request, token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == token).first()
    now = datetime.utcnow()
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < now:
        flash(request, "error", "Ссылка на сброс больше не действует.")
        return RedirectResponse(url=request.url_for("forgot_password"), status_code=303)

    if request.method == "POST":
        form_raw = await request.form()
        form = parse_form_data(form_raw)
        if not ensure_csrf(request, form):
            return RedirectResponse(url=request.url_for("reset_password", token=token), status_code=303)
        new_password = form.get("password", "")
        if not new_password:
            flash(request, "error", "Введите новый пароль.")
        else:
            user.set_password(new_password)
            user.reset_token = None
            user.reset_token_expires_at = None
            db.commit()
            flash(request, "success", "Пароль обновлён.")
            return RedirectResponse(url=request.url_for("login"), status_code=303)

    return await render(
        request,
        "reset_password.html",
        {"request": request, "token": token, "current_user": None},
    )


@router.api_route("/profile", methods=["GET"], response_class=HTMLResponse)
async def profile(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        flash(request, "error", "Нужно авторизоваться.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.id.desc()).all()
    cart_entries = []
    cart = get_cart(request)
    items_map = {item.id: item for item in db.query(Item).all()}
    for idx, entry in enumerate(cart):
        item = items_map.get(entry.get("item_id"))
        if not item:
            continue
        cart_entries.append(
            {
                "id": f"cart-{idx+1}",
                "item_name": item.name,
                "period": f"{entry.get('start_at') or '—'} — {entry.get('end_at') or '—'}",
                "status": "В корзине",
            }
        )
    return await render(
        request,
        "profile.html",
        {"request": request, "orders": orders, "current_user": user, "cart_entries": cart_entries},
    )


@router.api_route("/profile/edit", methods=["GET", "POST"], response_class=HTMLResponse)
async def edit_profile(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        flash(request, "error", "Нужно авторизоваться.")
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    if request.method == "POST":
        form_raw = await request.form()
        form = parse_form_data(form_raw)
        if not ensure_csrf(request, form):
            return RedirectResponse(url=request.url_for("edit_profile"), status_code=303)
        full_name = form.get("full_name", "").strip()
        email = form.get("email", "").strip().lower()
        new_password = form.get("new_password", "")

        if not (full_name and email):
            flash(request, "error", "Имя и email обязательны.")
        elif email != user.email and db.query(User).filter(User.email == email).first():
            flash(request, "error", "Такой email уже занят.")
        else:
            user.full_name = full_name
            if email != user.email:
                user.email = email
                user.email_confirmed = False
                user.confirmation_token = generate_token()
                db.commit()
                link = build_absolute_url(request, "confirm_email", token=user.confirmation_token)
                sent = send_email(
                    "Подтверждение email",
                    user.email,
                    f"Ссылка: {link}\nКод: {user.confirmation_token}",
                )
                flash(
                    request,
                    "success",
                    "Email обновлён. Подтвердите адрес" + ("" if sent else f": {link}"),
                )
            if new_password:
                user.set_password(new_password)
                flash(request, "success", "Пароль обновлён.")
            db.commit()
            return RedirectResponse(url=request.url_for("profile"), status_code=303)

    return await render(
        request,
        "edit_profile.html",
        {"request": request, "current_user": user},
    )
