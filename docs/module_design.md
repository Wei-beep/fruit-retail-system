# 模块设计

当前版本已进入真实硬件/YOLO 联调阶段：USB 摄像头、ONNX YOLO 推理、HX711 称重均已实现并默认启用（`config.yaml` 中三者 `mode` 默认 `real`），Mock 模式作为可切换的开发/调试备选保留。业务流程由 `workflow` 编排，GUI 不直接访问 SQL，数据库操作统一由 `repositories.py` 封装。

## core

`app/core` 保存配置加载、常量和业务异常。`config.py` 从项目根目录读取 `config.yaml`，并提供项目相对路径解析。

## db

`app/db` 负责 SQLite 连接、建表、初始化默认数据和仓储函数。`schema.sql` 定义 `products`、`transactions`、`calibration` 三张表。

## vision

`app/vision` 定义果蔬识别接口 `predict(frame: np.ndarray) -> dict`。`MockFruitVegetableDetector` 固定返回 `apple`；`YOLODetector` 已完整实现，基于 ONNX Runtime（锁定 3 线程 CPU 推理）、256×256 中心裁剪预处理，支持 65 类果蔬，返回 `{label, confidence, zh_name}`，并兼容 `str` 路径与 `np.ndarray` 两种输入。

## camera

`app/camera` 定义图片采集接口，`capture()` 返回 `np.ndarray`（内存直传），并提供 `get_stream_frame()` 供 GUI 视频流取帧。`MockCamera` 返回测试图解码矩阵或全黑占位矩阵；`USBCamera` 已完整实现：延迟导入 `cv2`、常开设备、缓冲区设为 1，`capture()` 连读清缓存后抓拍。

## weighing

`app/weighing` 定义称重接口（返回 kg 的 `float`）。`MockWeightSensor` 模拟稳定重量，`StabilityDetector` 判断滑动窗口是否稳定；`HX711Sensor` 已完整实现，通过 RPi.GPIO 位操作读取 24 位 ADC，结合 `calibration` 表参数换算 kg，支持去皮、平均采样和电源管理。`CalibrationService` 负责校准参数读写。

## pricing

`app/pricing` 包含价格查询、价格更新、总价计算和交易记录服务。总价保留两位小数。

## workflow

`app/workflow/transaction_flow.py` 串联称重、拍照、识别、查价和计价。`prepare_transaction()` 只生成待确认交易，`confirm_transaction()` 才写入数据库。

## gui

`app/gui` 使用 Tkinter 实现 800x480 窗口（默认 `fullscreen: true`）。`main_window.py` 负责界面展示，并按 `config.yaml` 各模块 `mode` 实例化对应的 camera/sensor/detector，集成右侧实时视频流面板（约 30 FPS，PIL 缩放渲染）；`gui_controller.py` 负责后台线程、确认、清除和退出（`stop()`）逻辑；界面右上角的“✕”退出按钮经 `MainWindow._on_close()` 停止后台线程并销毁窗口。`performance_monitor.py` 提供可选的后台性能监控（FPS/CPU/内存，依赖 psutil，由 `gui.monitor_performance` 开关）。

## api

`app/api` 保留 FastAPI 服务结构。当前 `GET /health` 可用，价格和交易接口提供基础实现，后续可扩展鉴权、校验和设备状态接口。

## scripts

`scripts` 提供初始化数据库（`init_db.py`）、启动 GUI/API（`run_gui.py`/`run_api.py`）、完整 HX711 校准（`calibrate_scale.py`）、拍照测试（`capture_test_image.py`）、把 `label_map.json` 全部 65 类同步进 `products`（`sync_db.py`）、YOLO 测速（`speed_test.py`）、摄像头实时流测试（`stream_test.py`）和 HX711 实时读数验证（`weighing_test.py`）入口。各脚本经 `_bootstrap.py` 把项目根注入 `sys.path`。

## tests

`tests` 提供基础 pytest 测试，覆盖稳定检测、计价计算和 Mock 交易流程。
