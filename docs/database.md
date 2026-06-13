# 数据库设计

数据库使用 SQLite，默认路径为 `data/app.db`。在项目根目录激活 `.venv` 后，由 `python scripts/init_db.py` 创建。

## products

用于保存果蔬价格。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 主键 |
| label | TEXT UNIQUE NOT NULL | 识别标签 |
| name_cn | TEXT NOT NULL | 中文名称 |
| price_per_kg | REAL NOT NULL | 每千克单价 |
| updated_at | TIMESTAMP | 更新时间 |

默认数据包括 `apple / 苹果 / 12.8`、`banana / 香蕉 / 8.5`、`orange / 橙子 / 10.0`。真实 YOLO 模式下可运行 `python scripts/sync_db.py`，将 `data/models/label_map.json` 中全部 65 类果蔬写入 `products`（默认单价 9.9 元/kg），供识别后查价。

## transactions

用于保存已确认交易。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 主键 |
| label | TEXT NOT NULL | 商品标签 |
| weight_kg | REAL NOT NULL | 重量 kg |
| price_per_kg | REAL NOT NULL | 单价 |
| total_price | REAL NOT NULL | 总价 |
| created_at | TIMESTAMP | 创建时间 |

`prepare_transaction()` 不写入该表。只有用户在 GUI 点击“确认”后，`confirm_transaction()` 才写入。

## calibration

用于保存 HX711 称重校准参数。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 主键 |
| scale_factor | REAL NOT NULL | 缩放系数 |
| offset | REAL NOT NULL | 零点偏移 |
| updated_at | TIMESTAMP | 更新时间 |

初始化时插入默认值 `scale_factor=1.0`、`offset=0.0`；运行 `scripts/calibrate_scale.py` 后写入真实校准参数。`weighing.mode: real` 时 `HX711Sensor` 启动会从该表读取参数换算 kg 重量（GUI 不直接读写该表）。
