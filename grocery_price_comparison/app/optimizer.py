"""
Core optimization engine.

Strategy:
  For every non-empty subset of stores (2^5 = 32 total), we assign each cart
  item to the cheapest store within that subset, then compute the full cost
  (goods + delivery fees where applicable).  We surface the top-N unique
  results sorted by total cost and label them meaningfully.
"""

from itertools import combinations
from typing import Dict, List, Optional, Tuple

from .models import (
    CartItem, CartRequest, OptimizationResult, OptimizeResponse,
    OrderLineItem, PurchaseMode, StoreOrder,
)
from .data import PRICES, PRODUCTS, STORES

_PRODUCTS_BY_ID: Dict[str, dict] = {p["id"]: p for p in PRODUCTS}


def _price(product_id: str, store_id: str) -> Optional[float]:
    return PRICES.get(product_id, {}).get(store_id)


def _evaluate_subset(
    items: List[CartItem],
    subset: Tuple[str, ...],
    mode: PurchaseMode,
) -> Optional[OptimizationResult]:
    """
    Assign each item to the cheapest available store in subset.
    Returns None if any item cannot be fulfilled by any store in the subset.
    """
    # store_id -> list of (CartItem, unit_price)
    assignments: Dict[str, List[Tuple[CartItem, float]]] = {s: [] for s in subset}

    for item in items:
        candidates = [
            (s, _price(item.product_id, s))
            for s in subset
            if _price(item.product_id, s) is not None
        ]
        if not candidates:
            return None
        best_store, best_price = min(candidates, key=lambda x: x[1])
        assignments[best_store].append((item, best_price))

    orders: List[StoreOrder] = []
    goods_total = 0.0
    delivery_total = 0.0

    for store_id in subset:
        assigned = assignments[store_id]
        if not assigned:
            continue

        store_cfg = STORES[store_id]
        line_items: List[OrderLineItem] = []
        subtotal = 0.0

        for cart_item, unit_price in assigned:
            product = _PRODUCTS_BY_ID[cart_item.product_id]
            line_total = unit_price * cart_item.quantity
            subtotal += line_total
            line_items.append(OrderLineItem(
                product_id=cart_item.product_id,
                product_name=product["name"],
                quantity=cart_item.quantity,
                unit_price=unit_price,
                line_total=round(line_total, 2),
            ))

        goods_total += subtotal
        meets_min = subtotal >= store_cfg["min_order"]

        delivery_fee = 0.0
        free_thr = None
        to_free = None

        if mode == PurchaseMode.DELIVERY:
            free_thr = store_cfg["free_delivery_from"]
            if subtotal >= free_thr:
                delivery_fee = 0.0
                to_free = 0.0
            else:
                delivery_fee = store_cfg["delivery_fee"]
                to_free = round(free_thr - subtotal, 2)
            delivery_total += delivery_fee

        orders.append(StoreOrder(
            store_id=store_id,
            store_name=store_cfg["name"],
            store_color=store_cfg["color"],
            items=line_items,
            goods_subtotal=round(subtotal, 2),
            delivery_fee=round(delivery_fee, 2),
            store_total=round(subtotal + delivery_fee, 2),
            meets_min_order=meets_min,
            free_delivery_threshold=free_thr,
            amount_to_free_delivery=to_free,
        ))

    # Sort orders by store name for consistent display
    orders.sort(key=lambda o: o.store_name)

    n_stores = len(orders)
    if n_stores == 1:
        label = orders[0].store_name
        description = f"Всё в одном магазине — {orders[0].store_name}"
    else:
        names = " + ".join(o.store_name for o in orders)
        label = names
        description = f"Разбить заказ на {n_stores} магазина: {names}"

    return OptimizationResult(
        label=label,
        description=description,
        stores_used=[o.store_id for o in orders],
        orders=orders,
        goods_total=round(goods_total, 2),
        delivery_total=round(delivery_total, 2),
        total_cost=round(goods_total + delivery_total, 2),
    )


def optimize(request: CartRequest) -> OptimizeResponse:
    store_ids = list(STORES.keys())
    items = request.items
    mode = request.mode

    # Detect products not available anywhere
    missing: List[str] = []
    for item in items:
        if all(_price(item.product_id, s) is None for s in store_ids):
            missing.append(item.product_id)
    fulfillable = [i for i in items if i.product_id not in missing]

    if not fulfillable:
        return OptimizeResponse(mode=mode, results=[], missing_products=missing)

    seen_signatures: set = set()
    candidates: List[OptimizationResult] = []

    for r in range(1, len(store_ids) + 1):
        for subset in combinations(store_ids, r):
            result = _evaluate_subset(fulfillable, subset, mode)
            if result is None:
                continue
            # Deduplicate by actual stores used (items may not spread to all stores)
            sig = tuple(sorted(result.stores_used))
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)
            candidates.append(result)

    if not candidates:
        return OptimizeResponse(mode=mode, results=[], missing_products=missing)

    candidates.sort(key=lambda r: r.total_cost)

    worst_cost = max(r.total_cost for r in candidates)
    for r in candidates:
        r.savings_vs_worst = round(worst_cost - r.total_cost, 2)

    candidates[0].is_best = True

    # Return top 5 options; always include pure single-store options for reference
    single_store = [r for r in candidates if len(r.stores_used) == 1]
    multi_store = [r for r in candidates if len(r.stores_used) > 1]

    # Top result + up to 2 multi-store + all single-store options, capped at 8
    top = candidates[:1]
    extra = [r for r in multi_store if r not in top][:3]
    singles = [r for r in single_store if r not in top]
    results = top + extra + singles
    # Remove duplicates while preserving order
    seen = set()
    unique_results = []
    for r in results:
        sig = tuple(sorted(r.stores_used))
        if sig not in seen:
            seen.add(sig)
            unique_results.append(r)

    return OptimizeResponse(
        mode=mode,
        results=unique_results[:8],
        missing_products=missing,
    )
