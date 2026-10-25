from __future__ import annotations

from app.core.constants import MOCK_PRODUCT_LABEL, MOCK_PRODUCT_NAME_CN
from app.db import repositories
from app.db.database import get_connection, initialize_schema


# 仅一个明确的「测试专用」商品作为默认种子，供 Mock 闭环（MockFruitVegetableDetector
# 固定返回该 label）与测试查价使用。刻意不再用 apple/banana 等真实水果名，避免测试交易
# 与真实交易数据混淆。真实水果一律由 scripts/sync_db.py 按模型类别写入。
DEFAULT_PRODUCTS = [
    (MOCK_PRODUCT_LABEL, MOCK_PRODUCT_NAME_CN, 9.9),
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
