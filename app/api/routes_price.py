from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.exceptions import ProductNotFoundError
from app.pricing.price_service import PriceService

router = APIRouter(prefix="/api")
price_service = PriceService()


class PriceUpdateRequest(BaseModel):
    label: str
    name_cn: str
    price_per_kg: float


@router.get("/price")
def get_price(label: str) -> dict:
    try:
        return price_service.get_price(label)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/price")
def update_price(payload: PriceUpdateRequest) -> dict:
    price_service.update_price(payload.label, payload.name_cn, payload.price_per_kg)
    return {"status": "ok"}
