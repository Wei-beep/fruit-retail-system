from __future__ import annotations

from typing import Any

from app.db.database import get_connection


def _row_to_dict(row: Any | None) -> dict | None:
    return dict(row) if row is not None else None


def get_product_by_label(label: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, label, name_cn, price_per_kg, updated_at FROM products WHERE label = ?",
            (label,),
        ).fetchone()
    return _row_to_dict(row)


def list_products() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, label, name_cn, price_per_kg, updated_at FROM products ORDER BY name_cn"
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_product(label: str, name_cn: str, price_per_kg: float) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO products (label, name_cn, price_per_kg)
            VALUES (?, ?, ?)
            ON CONFLICT(label) DO UPDATE SET
                name_cn = excluded.name_cn,
                price_per_kg = excluded.price_per_kg,
                updated_at = CURRENT_TIMESTAMP
            """,
            (label, name_cn, price_per_kg),
        )


def create_transaction(label: str, weight_kg: float, price_per_kg: float, total_price: float) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO transactions (label, weight_kg, price_per_kg, total_price)
            VALUES (?, ?, ?, ?)
            """,
            (label, weight_kg, price_per_kg, total_price),
        )
        return int(cursor.lastrowid)


def list_transactions() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, label, weight_kg, price_per_kg, total_price, created_at
            FROM transactions
            ORDER BY id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_calibration() -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, scale_factor, offset, updated_at
            FROM calibration
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return _row_to_dict(row)


def save_calibration(scale_factor: float, offset: float) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO calibration (scale_factor, offset) VALUES (?, ?)",
            (scale_factor, offset),
        )
