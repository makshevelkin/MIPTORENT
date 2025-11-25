from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import BASE_DIR, SESSION_COOKIE_SAMESITE, SESSION_COOKIE_SECURE, SESSION_SECRET
from .seed import init_db
from .routes import admin, auth, cart, public

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=SESSION_COOKIE_SECURE,
    same_site=SESSION_COOKIE_SAMESITE,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(cart.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}


init_db()
