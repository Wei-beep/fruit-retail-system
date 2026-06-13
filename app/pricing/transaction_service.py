from __future__ import annotations

from app.db import repositories


class TransactionService:
    def calculate_total(self, weight_kg: float, price_per_kg: float) -> float:
        return round(weight_kg * price_per_kg, 2)

    def create_transaction(
        self,
        label: str,
        weight_kg: float,
        price_per_kg: float,
        total_price: float,
    ) -> int:
        return repositories.create_transaction(label, weight_kg, price_per_kg, total_price)

    def list_transactions(self) -> list[dict]:
        return repositories.list_transactions()
