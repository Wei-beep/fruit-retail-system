from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_price import router as price_router
from app.api.routes_transaction import router as transaction_router
from app.db.init_db import initialize_database


def create_app() -> FastAPI:
    initialize_database()
    app = FastAPI(title="Fruit Retail System API")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(price_router)
    app.include_router(transaction_router)
    return app


app = create_app()
