from fastapi import FastAPI
from app.db import Base, engine
from app import models
from app.routers import movements, stock, forecast, alerts

app = FastAPI(title="ABS Inventory & Procurement Assistant", version="0.1.0")

app.include_router(movements.router)
app.include_router(stock.router)
app.include_router(forecast.router)
app.include_router(alerts.router)

@app.get("/health")
def health():
	return {"status": "ok"}
