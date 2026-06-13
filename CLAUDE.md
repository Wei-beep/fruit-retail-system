# CLAUDE.md

本文件适用于 `fruit_retail_system/` 整个项目。当前没有发现子目录存在独立工程配置或独立开发约定，因此暂不创建局部 `CLAUDE.md`。

## 项目现状

这是一个面向 Raspberry Pi 触摸屏场景的果蔬识别与零售计价系统。当前已进入真实硬件/YOLO 联调阶段：USB 摄像头（常开模式，内存直传）、YOLO ONNX 推理引擎（3 线程锁死，支持 65 类果蔬识别）、HX711 称重驱动均已实现并接入 GUI。`config.yaml` 中 `camera.mode`、`vision.mode`、`weighing.mode` 默认均已切换为 `real`。

Mock 模式保留作为开发/调试备选，仍可切换回 `mock` 运行。后续改代码时要保持 camera/mode、vision/mode、weighing/mode 三者均可通过配置独立切换，不要为了接入真实硬件破坏 Mock 闭环。

## 技术栈

- Python 3，当前本地虚拟环境为 `.venv/`。
- SQLite，使用标准库 `sqlite3`，默认数据库路径为 `data/app.db`。
- Tkinter GUI，默认 800x480，面向 Raspberry Pi DSI 7 寸触摸屏，包含实时视频流渲染。
- YAML 配置，依赖 `pyyaml`，配置文件为 `config.yaml`。
- FastAPI + uvicorn，当前 API 为预留和基础接口。
- pytest 基础测试。
- OpenCV（**已启用**）：USB 摄像头采集、YOLO 预处理均依赖 `cv2`；Mock 模式不应依赖它。
- ONNX Runtime：`YOLODetector` 使用 `onnxruntime` 进行 CPU 推理，固定 3 线程。
- Pillow：GUI 视频流渲染依赖 `PIL.Image` 做格式转换与缩放。
- psutil：GUI 后台性能监控线程（FPS、CPU、内存占用）依赖此库。

## 目录结构

- `app/core/`：配置加载、项目路径解析、常量、异常、显示环境设置。
- `app/db/`：SQLite 连接、schema、数据库初始化、仓储函数。业务层不要直接散落 SQL。
- `app/vision/`：识别接口、Mock 识别器、真实 YOLO 预留入口。
- `app/camera/`：摄像头接口、Mock 摄像头、USB 摄像头预留实现。
- `app/weighing/`：称重接口、Mock 称重、稳定检测、HX711 与校准预留。
- `app/pricing/`：价格查询/更新、总价计算、交易记录服务。
- `app/workflow/`：交易流程编排。`prepare_transaction()` 只生成待确认交易，`confirm_transaction()` 才写入数据库。
- `app/gui/`：Tkinter 界面和 GUI 控制器。GUI 调用业务层，不直接访问 SQL。
- `app/api/`：FastAPI 服务和基础价格/交易路由。GUI 当前不依赖 API。
- `scripts/`：数据库初始化、GUI/API 启动、校准提示、拍照测试、YOLO 测速、标签同步、摄像头测试、称重验证入口。
- `tests/`：基础 pytest 测试，覆盖稳定检测、计价和 Mock 交易流程。
- `docs/`：模块设计、Mock 模式、数据库、API、硬件接线、校准说明。
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
python scripts/run_gui.py
python main.py
python scripts/run_api.py
python scripts/calibrate_scale.py
python scripts/capture_test_image.py
python scripts/sync_db.py
python scripts/speed_test.py
python scripts/stream_test.py
python scripts/weighing_test.py
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
- 真实硬件和真实 YOLO 逻辑只能在既有预留位置扩展：`app/camera/usb_camera.py`、`app/weighing/hx711_sensor.py`、`app/weighing/calibration.py`、`app/vision/detector.py` 以及相关脚本。
- 识别器接口应保持 `predict(frame: np.ndarray) -> dict`，返回至少包含 `label` 和 `confidence`。已统一为内存直传，不再走硬盘路径。
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

- `MockWeightSensor` 模拟重量逐步稳定到约 `0.52 kg`。
- `StabilityDetector` 使用固定长度滑动窗口，窗口满且最大值与最小值差不超过阈值即稳定。
- `MockCamera` 已适配内存直传：`capture()` 返回 `np.ndarray`。优先读取 `data/images/test/` 下第一张 `jpg/jpeg/png`（动态导入 cv2 解码为 BGR 矩阵）；找不到图片或未安装 OpenCV 时返回一张 640x480 全黑 `np.zeros` 占位矩阵。`get_stream_frame()` 同样返回全黑占位帧。
- `MockFruitVegetableDetector` 固定返回 `{"label": "apple", "confidence": 0.97}`。
- 初始化数据库会创建 `products`、`transactions`、`calibration` 三张表，并 upsert `apple`、`banana`、`orange` 默认价格。
- `scripts/calibrate_scale.py` 已完整实现：空载去皮 → 多点放砝码采集 → 过原点线性回归计算 `scale_factor` → 写入 `calibration` 表 → 空载回零验证；直接驱动真实 `HX711Sensor`（无 mock 分支，初始化失败即退出）。
- `HX711Sensor` 已完整实现：使用 RPi.GPIO 驱动树莓派 GPIO，通过位操作读取 HX711 24 位 ADC 值，结合 `calibration` 表参数返回 kg 重量。支持 `tare()` 去皮、`read_raw_average()` 平均采样、`power_down/up()` 电源管理。引脚通过 `config.yaml` 的 `weighing.dout_pin/sck_pin` 配置。
- `YOLODetector` 已完整实现：支持 65 类果蔬分类，通过 ONNX Runtime 3 线程 CPU 推理，输入预处理为 256x256 中心裁剪，返回 `{"label", "confidence", "zh_name"}` 格式字典。`predict()` 同时兼容 `str`（路径）和 `np.ndarray`（内存矩阵）两种输入。
- `USBCamera` 已完整实现：常开设备，缓冲区设为 1 防止拍到过期帧，`capture()` 连读 3 次清缓存后抓拍，`get_stream_frame()` 为 GUI 视频流提供实时画面。
- `camera_interface.py` 的 `capture()` 方法签名已从返回文件路径改为返回 `np.ndarray`（内存直传）。
- GUI 已集成实时视频流：通过 `camera.get_stream_frame()` 拉取帧，PIL 缩放后渲染到右侧面板，维持约 30 FPS。
- GUI 包含后台性能监控：每 2 秒打印一次渲染 FPS、App CPU、系统 CPU、内存占用（依赖 `psutil`）。
- `scripts/sync_db.py` 可将 `label_map.json` 中全部 65 类果蔬写入 `products` 表（含默认单价 9.9 元/kg），供真实 YOLO 模式下查价使用。
- `scripts/speed_test.py` 提供独立的 YOLO ONNX 模型批量测速，输出单张推理耗时和等效 FPS。
- `scripts/stream_test.py` 提供独立的 USB 摄像头实时流测试，显示实时 FPS。
- `scripts/weighing_test.py` 提供 HX711 传感器实时读数验证，持续打印原始值和 kg 重量。

## 待确认项

- 文档称 API 是"预留模块，不是本阶段核心验收目标"，但代码中已经提供 `GET /api/price`、`PUT /api/price`、`POST /api/transaction`、`GET /api/transactions` 的基础实现。后续需要确认这些接口是否进入稳定对外契约。
- `tests/test_transaction_flow.py` 使用默认 `data/app.db` 并会真实新增交易记录。是否需要改为临时测试数据库，需另行确认。
