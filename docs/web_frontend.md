# Web 前端（Chromium kiosk）

新增的浅色超市风触摸前端，运行在树莓派本地 Chromium kiosk 中，作为**默认 UI**。
旧的 Tkinter 前端保留，可通过配置切回。两者共用同一套业务层
（`TransactionFlow` / `GUIController` / `create_transaction_flow`），互不影响。

## 选择前端 / 启动

`config.yaml` 的 `gui` 段：

```yaml
gui:
  frontend: web        # web(默认 Chromium kiosk) | tk(旧 Tkinter)
  web_port: 8000       # web 服务端口(127.0.0.1)
  launch_browser: true # false 则只起服务、手动开浏览器调试
```

```bash
python main.py            # 按 gui.frontend 分发
python scripts/run_web.py # 直接起 Web kiosk（等价于 frontend=web）
```

`run_web()` 在本进程内起 uvicorn（守护线程）→ 探活 `/healthz` → 用
`chromium-browser`（找不到则回退 `chromium`）以 `--kiosk --app=...` 全屏打开本地页面，
阻塞等浏览器退出后收尾。HX711/摄像头由 Web 应用在该单进程内创建一次（单属主），
避免并发位操作。调试时设 `launch_browser: false`，再手动用浏览器打开
`http://127.0.0.1:8000`。

## 接口

`app/web` 自带 FastAPI 应用（独立于 `app/api` 的对外 REST）：

| 端点 | 说明 |
| --- | --- |
| `GET /` | kiosk 页面（`app/web/static/index.html`） |
| `GET /healthz` | 探活 |
| `GET /api/ui/products` | 品类选择器全量商品 `[{label,name_cn,price_per_kg}]` |
| `POST /api/exit` | 前端「退出」确认后调用，置位关停信号→ `launcher` 终止 Chromium 并结束 kiosk 进程，返回 `{"status":"exiting"}` |
| `GET /stream/video` | MJPEG 视频流（`multipart/x-mixed-replace`） |
| `WS /ws` | 实时状态双工通道 |

### WebSocket 协议

服务端 → 前端：

| type | 字段 | 含义 |
| --- | --- | --- |
| `weight` | `weight_g`(int,已舍小数), `stable`(bool), `triggered`(bool) | 实时重量；`triggered` 表示是否超过触发阈值(`weighing.trigger_threshold_kg`，默认 20g)。空闲态 `triggered=false` 时前端只显示「请放置」引导、不显示克重，超过阈值后才显示实时重量 |
| `recognizing` | — | 重量稳定、识别中 |
| `transaction_ready` | `data` | 待确认（`low_confidence` 区分正常/低置信） |
| `confirmed` | `transaction_id`, `data` | 已确认，进入支付引导 |
| `cleared` | — | 回到空闲 |
| `error` | `text` | 异常提示 |

`data` 结构（低置信时 `name_cn/price_per_kg/total_price` 为 `null`）：

```json
{ "label": "apple_fuji", "name_cn": "红富士苹果", "confidence": 0.96,
  "weight_kg": 0.326, "price_per_kg": 12.8, "total_price": 4.17,
  "low_confidence": false,
  "candidates": [{"label": "...", "zh_name": "...", "confidence": 0.41}] }
```

前端 → 服务端：`{"type":"confirm"}` / `{"type":"clear"}` / `{"type":"select","label":"..."}`。

## 界面状态

①空闲请放置（未触发只显示醒目引导文案，秤上物重超过触发阈值后才显示实时克重）
②识别中 ③待确认（核心）④低置信兜底（橙色警示 + top-3 候选 + 手动选择）
⑤全屏品类选择器（分类 Tab〔由 `label` 英文前缀派生〕+ 4 列网格 + 搜索）
⑥扫码支付引导（订单小票 + 微信/支付宝二维码占位，"完成"→ 回到空闲）。

低置信时由用户点候选或在品类选择器中手动选品，后端按当前重量重新计价
（`GUIController.select_label`）。

点「完成」后回到空闲引导，但**不会立刻**开始下一轮称重：后端先等秤面重量回落到
触发阈值以下（已购商品被取走）再重新进入称重→识别流程，避免商品仍在秤上时被重复
识别（`TransactionFlow.wait_for_release`）。注：mock 称重恒有载重，不会自动重新进入
下一轮，属预期（mock 模拟「秤上一直有物」）。

## 界面语言（中 / EN）

顶栏右上角、✕ 左侧有一个「中 / EN」分段开关，默认「中」。点击纯前端热切换全站界面文案
（无需刷新、不经后端）：静态文本走 HTML 的 `data-i18n` / `data-i18n-ph` / `data-i18n-alt`
/ `data-i18n-aria`，动态面板（待确认/低置信/支付/选择器）由各 render 函数读 `t()` 并在
切换时重渲染（文案表见 `app.js` 顶部 `I18N`）。

该开关只出现在 **放置 → 识别 → 确认** 主界面：品类选择器与扫码支付都是 `z-index` 更高的
全屏遮罩，会盖住整条顶栏（连同 ✕），故支付页天然不显示开关——切换仍是全局生效，回到主
界面或重开遮罩即为对应语言。商品名取自后端 `name_cn`（库内无英文名），属数据而非界面文案，
不随开关翻译。

## 前端开发 / 视觉走查

前端为原生 HTML/CSS/JS，无构建步骤，静态资源全部本地化（离线友好）。
访问 `http://127.0.0.1:8000/?demo=1` 进入演示模式：无需后端/硬件，用内置假数据
依次轮播全部 6 个状态（点击或空格手动切换），便于审查视觉。

## 文件

- `app/web/server.py`：FastAPI 应用工厂（StaticFiles + REST + WS + MJPEG）。
- `app/web/session.py`：组装业务流程 + 控制器，单生产者取帧线程。
- `app/web/broadcaster.py`：线程安全的 WebSocket 广播。
- `app/web/launcher.py`：`run_web()` 启动器（uvicorn + Chromium）。
- `app/web/static/`：`index.html` / `styles.css` / `app.js`。
