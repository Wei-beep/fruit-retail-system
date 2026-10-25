# CLAUDE.md

## 项目现状

这是一个面向 Raspberry Pi 触摸屏场景的果蔬识别与零售计价系统。当前已进入真实硬件/YOLO 联调阶段：USB 摄像头（常开模式，内存直传）、YOLO11 ONNX 目标检测引擎（3 线程锁死，支持 71 类果蔬识别，含多目标计数）、HX711 称重驱动均已实现并接入前端。`config.yaml` 中 `camera.mode`、`vision.mode`、`weighing.mode` 默认均已切换为 `real`。

前端有两套，由 `config.yaml` 的 `gui.frontend` 切换：默认 `web`（Chromium kiosk，`app/web`），保留 `tk`（旧 Tkinter，`app/gui`）。两者共用业务层（`create_transaction_flow` / `GUIController` / `TransactionFlow`），互不影响。

Mock 模式保留作为开发/调试备选，仍可切换回 `mock` 运行。后续改代码时要保持 camera/mode、vision/mode、weighing/mode 三者均可通过配置独立切换，不要为了接入真实硬件破坏 Mock 闭环。

## 技术栈

- Python 3 + `.venv/`；SQLite（标准库 `sqlite3`，`data/app.db`）；YAML 配置（`pyyaml`，`config.yaml`）。
- 前端：Tkinter（800x480 触摸屏）/ FastAPI + uvicorn（`app/web` Web kiosk，WS+MJPEG，依赖 `websockets`；`app/api` 为对外预留）。
- 视觉/采集：OpenCV（`cv2`，含 `cv2.dnn.NMSBoxes` 后处理，Mock 不依赖）、ONNX Runtime（`YOLODetector`，YOLO11 检测，3 线程 CPU 推理）、Pillow（GUI 渲染）。
- 测试 pytest（Web 层依赖 `httpx`）；GUI 性能监控依赖 `psutil`。

## 目录结构

- `app/core/`：配置加载、项目路径解析、常量、异常、显示环境设置。
- `app/db/`：SQLite 连接、schema、数据库初始化、仓储函数。业务层不要直接散落 SQL。
- `app/vision/`：识别接口、Mock 识别器、YOLO ONNX 识别引擎（已实现）。
- `app/camera/`：摄像头接口、Mock 摄像头、USB 摄像头驱动（已实现）。
- `app/weighing/`：称重接口、Mock 称重、稳定检测、HX711 驱动与校准服务（已实现）。
- `app/pricing/`：价格查询/更新、总价计算、交易记录服务。
- `app/workflow/`：交易流程编排（`transaction_flow.py`）与组装工厂（`factory.py` 的 `create_transaction_flow`，前端共用）。`prepare_transaction()` 只生成待确认交易，`confirm_transaction()` 才写入数据库。
- `app/gui/`：Tkinter 界面和 GUI 控制器（前端之一）。GUI 调用业务层，不直接访问 SQL。
- `app/web/`：默认 Web kiosk 前端（FastAPI 应用 + 原生静态页 `static/`）。复用业务层，提供 WS/MJPEG/品类接口。与 `app/api` 职责分离。
- `app/api/`：FastAPI 对外预留服务和基础价格/交易路由。本地前端闭环不依赖它。
- `scripts/`：数据库初始化、GUI/Web/API 启动、称重校准、拍照测试、YOLO 测速、标签同步、摄像头测试、称重验证（命令行与全屏 GUI）入口。
- `tests/`：基础 pytest 测试，覆盖稳定检测、计价、Mock 交易流程和 Web 层。
- `docs/`：模块设计、Mock 模式、数据库、API、Web 前端、硬件接线、校准说明。
- `data/`：本地数据库、测试/采集图片、模型文件（`best.pt`、`best.onnx` 等）。不要提交或依赖大型生成数据。

## 常用命令

所有 Python 相关命令默认在 `fruit_retail_system/` 目录下运行，并且必须先激活当前项目的 `.venv`。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
python scripts/init_db.py
python main.py                # 按 gui.frontend 启动默认前端(web)
python scripts/run_web.py     # 直接启动 Web kiosk 前端
python scripts/run_gui.py     # 启动旧 Tkinter 前端
python scripts/run_api.py
python scripts/calibrate_scale.py
python scripts/capture_test_image.py
python scripts/sync_db.py
python scripts/speed_test.py
python scripts/stream_test.py
python scripts/weighing_test.py
python scripts/weighing_test_gui.py
```

API 默认监听 `127.0.0.1:8000`：

```bash
curl http://127.0.0.1:8000/health
```

测试命令：

```bash
python -m pytest
```

当前项目没有 `pyproject.toml`、`setup.cfg`、`.flake8`、`ruff.toml`、Makefile 或 package scripts，也没有已配置的格式化/lint 命令。不要擅自引入新的 lint/format 工具配置；如需新增，应先说明原因并保持改动独立。

## 优先阅读的设计文档

改代码前按任务范围优先阅读：

1. `docs/module_design.md`：整体分层、模块职责、Mock 闭环边界。
2. `docs/mock_mode.md`：当前默认运行模式和 Mock 组件行为。
3. `docs/database.md`：SQLite 表结构、默认数据、交易写入时机。
4. `docs/api.md`：API 当前状态和预留接口，涉及 `app/api/` 时阅读。
5. `docs/hardware_wiring.md`：涉及 Raspberry Pi 显示、HX711、USB 摄像头时阅读。
6. `docs/calibration.md`：涉及称重校准或 `calibration` 表时阅读。

## 必须遵守的代码边界

- 保持 `config.yaml` 中默认 `camera.mode`、`weighing.mode`、`vision.mode` 可根据开发阶段切换；当前 camera、vision、weighing 三者默认均使用 `real`，Mock 模式仍可作为开发/调试备选通过配置切回。
- 称重模块已实现并默认启用（`app/weighing/hx711_sensor.py`，`weighing.mode: real`）；首次使用前必须运行 `scripts/calibrate_scale.py` 完成校准。
- 不要让 Mock 模式依赖 OpenCV、真实 YOLO 包、GPIO/HX711 库或硬件设备。
- 真实硬件和真实 YOLO 逻辑只能在既有实现位置扩展：`app/camera/usb_camera.py`、`app/weighing/hx711_sensor.py`、`app/weighing/calibration.py`、`app/vision/detector.py` 以及相关脚本。
- 识别器接口应保持 `predict(frame: np.ndarray) -> dict`，返回至少包含 `label` 和 `confidence`；`candidates`（top-3）、`count`（该类检出个数，供重数比异常校验）为可选附加键，Tk 路径忽略，Web 低置信兜底使用 `candidates`。
- 两套前端共用 `create_transaction_flow`/`GUIController`；扩展业务层时新增参数必须带默认值以保持 Tk 现状（如 `prepare_transaction(include_candidates=False)`、`GUIController(auto_restart_after_confirm=True)`）。Web 后端在 `app/web`，与 `app/api` 分离；Tk 前端闭环不得依赖任何服务进程。
- Web 模式单进程内只此一处持有摄像头/HX711（`KioskSession`），不要在 Web 路径再起第二个读取硬件的线程。HX711 的 ~±820/840g 假读数根因是并发抢占下 SCK 滞留拉高致芯片掉电，已由驱动用 mmap 位读取根治（见上条与 `docs/hardware_wiring.md`）；勿用互斥锁/限 cv2 线程/降 nice 等手段「修」它（实测无效）。
- 称重接口应返回 kg 单位的 `float`。`TransactionFlow.wait_for_stable_weight()` 负责稳定判断和有效重量范围过滤。
- 交易流程必须保持"先生成待确认交易，用户确认后才写入 `transactions` 表"的语义。
- GUI 不直接写 SQL；数据库访问集中经过 `app/db/repositories.py`，业务逻辑经过 `pricing`、`workflow` 等服务层。
- `PriceService.get_price()` 依赖 `products.label` 查价；新增识别标签时同步考虑默认商品数据或价格维护入口。
- 总价计算当前由 `TransactionService.calculate_total()` 四舍五入到两位小数，不要在 GUI/API 中重复实现不同规则。
- 项目路径解析应使用 `app/core/config.py` 中的 `resolve_project_path()` / `get_project_root()`，避免依赖调用命令时的工作目录。
- `scripts/*.py` 入口通过 `scripts/_bootstrap.py` 注入项目根目录到 `sys.path`；新增脚本保持同样模式。
- 项目内运行 `python`、`pip` 前默认已经执行 `source .venv/bin/activate`；测试使用 `python -m pytest`，不要写成裸 `pytest`。
- 不要把 `.venv/`、`.pytest_cache/`、`__pycache__/`、运行生成图片、运行生成数据库、大模型权重等作为业务代码改动处理。
- 修改数据库 schema 时，同步检查 `app/db/init_db.py`、`app/db/repositories.py`、`docs/database.md` 和相关测试。
- 修改 GUI 时注意默认 800x480 触摸屏和 `fullscreen: true` 场景，不要引入需要键盘/鼠标才能完成核心交易的交互。
- 修改 API 时注意当前 GUI 不依赖 API；不要把本地 GUI 闭环改成必须启动 API 才能运行。
- 测试应优先覆盖 Mock 模式核心路径。涉及数据库写入的测试会使用默认 `data/app.db`，新增测试前要避免依赖已有交易数量或固定运行顺序。

## 当前可确认的实现细节

- Mock（测试依赖）：`MockWeightSensor` 重量逐步稳定到约 `0.52 kg`；`MockFruitVegetableDetector` 固定返回测试商品 `{"label":"mock_item","confidence":0.97}`（label 见 `app/core/constants.py` 的 `MOCK_PRODUCT_LABEL`）；`MockCamera.capture()` 返回 ndarray（优先读 `data/images/test/` 首张图，否则 640x480 全黑）。Mock 不依赖 cv2/GPIO。
- `StabilityDetector`：固定长度滑动窗口，窗口满且极差不超阈值即稳定。
- 初始化数据库建 `products`/`transactions`/`calibration` 三表，并 upsert 唯一测试默认商品 `mock_item / 测试商品`（刻意不用真实水果名，避免测试交易与真实交易混淆）；真实水果一律由 `scripts/sync_db.py` 按模型类别写入。
- `camera_interface.capture()` 返回 `np.ndarray`（内存直传，非文件路径）。
- `HX711Sensor`：位读取 24 位 ADC，结合 `calibration` 表返回 kg。**时序关键的 25 个 SCK 脉冲用 mmap 直接读写寄存器（持 GIL 不被换出），勿改回纯 `RPi.GPIO`**——否则多线程负载下 SCK 滞留拉高致掉电、蹦出 ~±820/840g 假读数（详见 `docs/hardware_wiring.md`「时序与并发」）。

## 待确认项

- 文档称 API 是"预留模块，不是本阶段核心验收目标"，但代码中已经提供 `GET /api/price`、`PUT /api/price`、`POST /api/transaction`、`GET /api/transactions` 的基础实现。后续需要确认这些接口是否进入稳定对外契约。
- `tests/test_transaction_flow.py` 使用默认 `data/app.db` 并会真实新增交易记录。是否需要改为临时测试数据库，需另行确认。
