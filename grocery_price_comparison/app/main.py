from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data import PRODUCTS, STORES
from .models import CartRequest, OptimizeResponse
from .optimizer import optimize

app = FastAPI(
    title="Grocery Price Comparison",
    description="Сравнение цен в супермаркетах и оптимизация корзины",
    version="1.0.0",
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/products")
def list_products(
    q: Optional[str] = Query(None, description="Поиск по названию"),
    category: Optional[str] = Query(None, description="Фильтр по категории"),
):
    result = PRODUCTS
    if q:
        q_lower = q.lower()
        result = [p for p in result if q_lower in p["name"].lower()]
    if category:
        result = [p for p in result if p["category"] == category]
    return result


@app.get("/api/categories")
def list_categories():
    seen = []
    for p in PRODUCTS:
        if p["category"] not in seen:
            seen.append(p["category"])
    return seen


@app.get("/api/stores")
def list_stores():
    return list(STORES.values())


@app.post("/api/optimize", response_model=OptimizeResponse)
def optimize_cart(request: CartRequest):
    return optimize(request)


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
