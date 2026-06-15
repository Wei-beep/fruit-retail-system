"""把 label_map.json 中的全部 YOLO 类别同步进 products 表。

写库统一走 repositories.upsert_product（不直接拼 SQL），保证与业务层一致的 upsert 语义；
所有商品类型设置一个合理的统一初始单价（仅作占位，后续由价格维护入口逐项调整）。
"""
import _bootstrap  # noqa: F401

import json

from app.core.config import resolve_project_path
from app.db import repositories
from app.db.init_db import initialize_database

# 同步时给所有类别的统一初始单价（元/kg）。仅作初始占位，后续可逐项调整；改这一个常量即可。
DEFAULT_PRICE_PER_KG = 9.9


def sync_labels_to_db() -> None:
    label_path = resolve_project_path("data/models/label_map.json")

    print("🔄 开始执行数据注入...")

    if not label_path.exists():
        print(f"❌ 找不到字典文件: {label_path}")
        return

    # 确保 products 等表已建好（幂等），替代「db 不存在直接报错」的脆弱检查
    initialize_database()

    with label_path.open("r", encoding="utf-8") as f:
        label_map = json.load(f)

    labels: set[str] = set()
    for info in label_map.values():
        # label_map 中可能有重复 en（如索引 0/3 同为 apple_fuji），upsert 天然合并
        repositories.upsert_product(info["en"], info["zh"], DEFAULT_PRICE_PER_KG)
        labels.add(info["en"])

    print("-" * 40)
    print(f"✅ 数据库同步完成！共同步 {len(labels)} 种果蔬。")
    print(f"📊 统一初始单价：{DEFAULT_PRICE_PER_KG} 元/kg（后续可在价格维护入口逐项调整）。")
    print("🚀 请重新启动 main.py。")


if __name__ == "__main__":
    sync_labels_to_db()
