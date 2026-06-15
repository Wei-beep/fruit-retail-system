# API 状态

`app/api/` 是独立于 Web kiosk（`app/web`）的对外 REST 服务。除 `GET /health` 外，
价格与交易的基础接口均已实现（见 `app/api/routes_price.py`、`routes_transaction.py`）。
本地前端闭环（Tk / Web kiosk）**不依赖**此服务，可直接调用业务层；此 API 仅供外部系统
（如后台管理、对账）按需调用。

> 接口稳定性说明：以下接口为**基础实现**，尚未形式化对外契约——鉴权、统一错误码、
> 分页、请求体更严格的校验、版本化等均未补充。是否冻结为稳定对外契约仍待确认
> （见 `CLAUDE.md` 待确认项）。集成方请预期后续可能调整。

## 启动

```bash
source .venv/bin/activate
python scripts/run_api.py
```

监听地址取自 `config.yaml` 的 `api` 段，默认 `127.0.0.1:8000`。应用工厂
`app.api.server:create_app` 在启动时会调用 `initialize_database()`（建表 + upsert 默认商品）。

> 端口提示：Web kiosk（`gui.web_port`）默认也用 `8000`。若需与 kiosk 同时运行，
> 请改其中一方端口，避免端口冲突。

```bash
curl http://127.0.0.1:8000/health
```

## 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 探活 |
| `GET` | `/api/price?label=<label>` | 按 `label` 查单个商品价格 |
| `PUT` | `/api/price` | upsert 商品（名称 + 单价） |
| `POST` | `/api/transaction` | 直接写入一条交易记录 |
| `GET` | `/api/transactions` | 列出全部交易（按 `id` 倒序） |

### `GET /health`

```json
{"status": "ok"}
```

### `GET /api/price?label=apple`

成功（200）：

```json
{"label": "apple", "name_cn": "苹果", "price_per_kg": 12.8}
```

商品不存在（404）：

```json
{"detail": "商品不存在: <label>"}
```

### `PUT /api/price`

请求体：

```json
{"label": "apple", "name_cn": "苹果", "price_per_kg": 12.8}
```

行为：按 `label` upsert（存在则更新 `name_cn`/`price_per_kg` 并刷新 `updated_at`，
否则插入）。响应：

```json
{"status": "ok"}
```

### `POST /api/transaction`

请求体（四个字段均由调用方提供）：

```json
{"label": "apple", "weight_kg": 0.52, "price_per_kg": 12.8, "total_price": 6.66}
```

响应（新记录主键）：

```json
{"id": 1}
```

> 注意：此接口是**底层直写**，不经「先生成待确认交易、确认后再落库」的本地交易流程
> （`TransactionFlow.prepare_transaction` / `confirm_transaction`），也不重新计算 `total_price`，
> 调用方需自行保证字段一致。本地 kiosk 落库仍走业务层，不经此接口。

### `GET /api/transactions`

按 `id` 倒序返回全部交易：

```json
[
  {"id": 2, "label": "banana", "weight_kg": 0.3, "price_per_kg": 8.5,
   "total_price": 2.55, "created_at": "2026-06-16 10:00:00"},
  {"id": 1, "label": "apple", "weight_kg": 0.52, "price_per_kg": 12.8,
   "total_price": 6.66, "created_at": "2026-06-16 09:59:00"}
]
```

## 与 Web kiosk 的关系

`app/api`（对外 REST）与 `app/web`（本地 kiosk 的 FastAPI：静态页 + WS + MJPEG +
`/api/ui/products` + `/api/exit`）是两套互相独立的应用，职责分离。kiosk 的接口见
`docs/web_frontend.md`；GUI/kiosk 本地闭环不需要启动 `app/api`。
