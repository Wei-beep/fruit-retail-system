from __future__ import annotations

from app.db import repositories
from app.db.database import get_connection, initialize_schema


DEFAULT_PRODUCTS = [
    ("apple", "苹果", 12.8),
    ("banana", "香蕉", 8.5),
    ("orange", "橙子", 10.0),
]


def initialize_database() -> None:
    initialize_schema()
    for label, name_cn, price_per_kg in DEFAULT_PRODUCTS:
        repositories.upsert_product(label, name_cn, price_per_kg)

    with get_connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM calibration").fetchone()[0]
        if count == 0:
            connection.execute(
                "INSERT INTO calibration (scale_factor, offset) VALUES (?, ?)",
                (1.0, 0.0),
            )


if __name__ == "__main__":
    initialize_database()
