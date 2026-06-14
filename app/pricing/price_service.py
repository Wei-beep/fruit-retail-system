from __future__ import annotations

from app.core.exceptions import ProductNotFoundError
from app.db import repositories


class PriceService:
    def get_price(self, label: str) -> dict:
        product = repositories.get_product_by_label(label)
        if product is None:
            raise ProductNotFoundError(f"商品不存在: {label}")
        return {
            "label": product["label"],
            "name_cn": product["name_cn"],
            "price_per_kg": float(product["price_per_kg"]),
        }

    def update_price(self, label: str, name_cn: str, price_per_kg: float) -> None:
        repositories.upsert_product(label, name_cn, price_per_kg)

    def list_products(self) -> list[dict]:
        return [
            {
                "label": product["label"],
                "name_cn": product["name_cn"],
                "price_per_kg": float(product["price_per_kg"]),
            }
            for product in repositories.list_products()
        ]
