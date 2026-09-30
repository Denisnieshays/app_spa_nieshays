from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db import Base, engine
from app import models  # noqa: F401
from app.routers import movements, stock, forecast, alerts, chat, products, batches

app = FastAPI(title="ABS Inventory & Procurement Assistant", version="0.1.0")

app.include_router(movements.router)
app.include_router(stock.router)
app.include_router(forecast.router)
app.include_router(alerts.router)
app.include_router(chat.router)
app.include_router(products.router)
app.include_router(batches.router)

app.mount("/ui", StaticFiles(directory="app/static", html=True), name="ui")


@app.get("/health")
def health():
    return {"status": "ok"}
