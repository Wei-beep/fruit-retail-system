# API 状态

当前 API 为预留模块，不是本阶段核心验收目标。服务结构位于 `app/api/`，启动入口为：

```bash
source .venv/bin/activate
python scripts/run_api.py
```

## 当前可用接口

```text
GET /health
```

返回：

```json
{"status": "ok"}
```

## 计划接口

当前已提供基础版本，后续可补充更完整的校验、错误码、分页和设备状态。

```text
GET /api/price?label=apple
PUT /api/price
POST /api/transaction
GET /api/transactions
```

GUI 当前不依赖 API，直接调用本地业务层。
