from fastapi import FastAPI
from app.db import Base, engine
from app import models

app = FastAPI(title="ABS Inventory & Procurement Assistant", version="0.1.0")
@app.get("/health")
def health():
	return {"status": "ok"}
