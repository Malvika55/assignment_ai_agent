from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def normalize_order_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"ORD[-\s_]*?(\d+)", text, flags=re.IGNORECASE)
    if not match:
        return None
    return f"ORD-{match.group(1)}"


def _safe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe = []
    for item in items or []:
        safe.append(
            {
                "name": item.get("name"),
                "quantity": item.get("quantity"),
                "final_sale": item.get("final_sale"),
            }
        )
    return safe


def lookup_order(order_id: Any, orders_path: str | Path = "data/orders.json") -> dict[str, Any]:
    normalized = normalize_order_id(order_id)
    if not normalized:
        return {
            "error": "missing_or_invalid_order_id",
            "message": "I need a valid order ID such as ORD-1007 before I can look up the order.",
        }

    path = Path(orders_path)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    for order in payload.get("orders", []):
        if order.get("order_id") == normalized:
            customer = order.get("customer", {})
            status = order.get("status")
            safe = {
                "order_id": order.get("order_id"),
                "membership_tier": order.get("membership_tier"),
                "items": _safe_items(order.get("items") or []),
                "placed_at": order.get("placed_at"),
                "status": status,
                "status_updated_at": order.get("status_updated_at"),
                "shipped_at": order.get("shipped_at"),
                "delivered_at": order.get("delivered_at"),
                "carrier": order.get("carrier"),
                "tracking_number": order.get("tracking_number"),
                "estimated_delivery": order.get("estimated_delivery"),
                "customer_safe_message": order.get("customer_safe_message"),
            }
            safe["customer_name"] = customer.get("name")
            return safe

    return {
        "error": "not_found",
        "message": "I couldn’t find that order. Please check the order ID or contact support.",
    }


__all__ = ["lookup_order", "normalize_order_id"]
