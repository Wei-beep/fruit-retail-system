"""把 label_map.json 中的真实 YOLO 类别同步进 products 表（真正的「同步」：增 + 删）。

写库统一走 repositories（不直接拼 SQL），保证与业务层一致的 upsert 语义；
所有商品类型设置一个合理的统一初始单价（仅作占位，后续由价格维护入口逐项调整）。
同步后还会删除 products 中既不属于当前模型类别、也不属于 Mock 默认商品的历史遗留标签，
使 products 收敛为「当前模型真实类别 ∪ Mock 默认商品」，避免换模型后旧标签长期堆积。
"""
import _bootstrap  # noqa: F401

import json

from app.core.config import resolve_project_path
from app.db import repositories
from app.db.init_db import DEFAULT_PRODUCTS, initialize_database

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
    skipped = 0
    for info in label_map.values():
        label = info["label"]
        # class_xx_unknown 为占位类（数据集未匹配），不写入 products：
        # 业务层遇到该 label 时 get_price 抛 ProductNotFoundError → 正常转手动选品流程。
        if label.startswith("class_"):
            skipped += 1
            continue
        # label_map 中可能有重复 label（如索引 14/49/53 同为 banana_yellow），upsert 天然合并
        repositories.upsert_product(label, info["zh_name"], DEFAULT_PRICE_PER_KG)
        labels.add(label)

    # 清理历史遗留标签：保留「当前模型真实类别 ∪ Mock 默认商品」。
    # 保留 Mock 默认（apple/banana/orange）是因为 initialize_database 每次启动都会重新注入，
    # 且 Mock 识别器固定返回 apple，Mock 闭环/测试依赖其在库。
    keep = labels | {label for label, _, _ in DEFAULT_PRODUCTS}
    removed = repositories.delete_products_not_in(keep)

    print("-" * 40)
    print(f"✅ 数据库同步完成！共同步 {len(labels)} 种果蔬（跳过 {skipped} 个 class_xx_unknown 占位类）。")
    if removed:
        print(f"🧹 清理历史遗留旧标签 {removed} 个（不属于当前模型类别，也非 Mock 默认商品）。")
    print(f"📊 统一初始单价：{DEFAULT_PRICE_PER_KG} 元/kg（后续可在价格维护入口逐项调整）。")
    print("🚀 请重新启动 main.py。")


if __name__ == "__main__":
    sync_labels_to_db()
