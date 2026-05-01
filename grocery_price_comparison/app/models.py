from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class PurchaseMode(str, Enum):
    DELIVERY = "delivery"
    OFFLINE = "offline"


class CartItem(BaseModel):
    product_id: str
    quantity: float = Field(gt=0, default=1)


class CartRequest(BaseModel):
    items: List[CartItem]
    mode: PurchaseMode = PurchaseMode.DELIVERY


class OrderLineItem(BaseModel):
    product_id: str
    product_name: str
    quantity: float
    unit_price: float
    line_total: float


class StoreOrder(BaseModel):
    store_id: str
    store_name: str
    store_color: str
    items: List[OrderLineItem]
    goods_subtotal: float
    delivery_fee: float
    store_total: float
    meets_min_order: bool
    free_delivery_threshold: Optional[float] = None
    amount_to_free_delivery: Optional[float] = None


class OptimizationResult(BaseModel):
    label: str
    description: str
    stores_used: List[str]
    orders: List[StoreOrder]
    goods_total: float
    delivery_total: float
    total_cost: float
    savings_vs_worst: Optional[float] = None
    is_best: bool = False


class OptimizeResponse(BaseModel):
    mode: PurchaseMode
    results: List[OptimizationResult]
    missing_products: List[str]
