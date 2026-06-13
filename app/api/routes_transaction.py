from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.pricing.transaction_service import TransactionService

router = APIRouter(prefix="/api")
transaction_service = TransactionService()


class TransactionCreateRequest(BaseModel):
    label: str
    weight_kg: float
    price_per_kg: float
    total_price: float


@router.post("/transaction")
def create_transaction(payload: TransactionCreateRequest) -> dict:
    transaction_id = transaction_service.create_transaction(
        payload.label,
        payload.weight_kg,
        payload.price_per_kg,
        payload.total_price,
    )
    return {"id": transaction_id}


@router.get("/transactions")
def list_transactions() -> list[dict]:
    return transaction_service.list_transactions()
