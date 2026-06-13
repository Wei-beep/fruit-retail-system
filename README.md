# 基于 YOLO 的嵌入式果蔬识别与零售计价系统

英文名：An Embedded Fruit and Vegetable Recognition and Retail Pricing System Based on YOLO

## 项目简介

本项目面向嵌入式果蔬零售计价场景，目标是在 Raspberry Pi 等设备上接入称重传感器、摄像头、YOLO 识别模型和本地数据库，实现“称重、识别、查价、计价、确认交易”的完整业务流程。

当前已进入真实硬件/YOLO 联调阶段：
- **USB 摄像头**：常开模式，内存直传，已集成到 GUI 视频流
- **YOLO 识别**：基于 ONNX Runtime 的 65 类果蔬分类引擎，已接入交易流程
- **称重**：基于 RPi.GPIO 的 HX711 驱动已实现并默认启用（`weighing.mode: real`），首次使用前需运行校准脚本

Mock 模式保留作为开发/调试备选，可通过 `config.yaml` 切换回纯 Mock 运行。

## 当前实现范围

- `YOLODetector` 已完成：65 类果蔬分类，ONNX Runtime 3 线程 CPU 推理，256x256 中心裁剪预处理，支持内存矩阵和文件路径双输入。
- `USBCamera` 已完成：常开设备，缓冲区 1 防过期帧，`capture()` 连读 3 次清缓存后抓拍，`get_stream_frame()` 为 GUI 提供实时视频流。
- `HX711Sensor` 已完成：RPi.GPIO 位操作读取 24 位 ADC，结合 `calibration` 表参数换算 kg，支持去皮、平均采样和电源管理。
- `MockWeightSensor` 保留，模拟逐渐稳定到约 0.52 kg 的重量（Mock 模式备选）。
- `StabilityDetector` 使用滑动窗口判断重量稳定。
- `MockCamera` 保留，返回 `data/images/test/` 中的测试图片。
- `MockFruitVegetableDetector` 保留，固定返回 `apple` 和 `0.97` 置信度。
- SQLite `products` 表支持 65 类果蔬价格（通过 `scripts/sync_db.py` 同步）。
- Tkinter GUI 集成实时视频流，自动等待称重、识别、计价并显示待确认交易。
- 用户点击"确认"后写入 `transactions` 表，点击"清除"则取消当前待确认交易。
- GUI 右上角提供"✕"退出按钮，全屏无标题栏时也能关闭程序（退出时停止后台线程）。
- FastAPI 基础服务结构，`GET /health` 可用，价格/交易接口已实现。

## 当前未实现/简化的部分

- FastAPI 业务接口：`app/api/` 仅提供基础实现，鉴权、完整校验、分页和设备状态待补充
- 复杂 UI 美化和完整自动化测试体系

## 技术栈

- Python 3
- SQLite，使用标准库 `sqlite3`
- Tkinter GUI，默认窗口 800x480，面向已连接的 Raspberry Pi DSI 7 寸触摸屏
- YAML 配置，使用 `pyyaml`
- FastAPI 结构预留
- pytest 基础测试
- OpenCV：USB 摄像头采集、YOLO 预处理
- ONNX Runtime：YOLO CPU 推理，固定 3 线程
- Pillow：GUI 视频流渲染
- psutil：GUI 后台性能监控

## 目录结构

```text
app/core        配置、常量、异常
app/db          SQLite 连接、建表、初始化、仓储
app/vision      YOLO 接口、Mock 识别器、YOLO ONNX 引擎
app/camera      摄像头接口、Mock 摄像头、USB 摄像头驱动
app/weighing    称重接口、Mock 称重、稳定检测、HX711 驱动和校准服务
app/pricing     价格和交易服务
app/workflow    交易流程编排
app/gui         Tkinter 界面和控制器（含实时视频流）
app/api         FastAPI 服务和路由
scripts         初始化、运行 GUI/API、校准、拍照、测速、同步等脚本
data            数据库、图片和模型目录
tests           基础 pytest 测试
docs            模块、Mock、数据库、硬件、API、校准说明
```

## 安装依赖

本项目下运行 Python 命令前，默认先进入项目目录并激活当前虚拟环境：

```bash
cd /home/pi/project/fruit_retail_system
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` 已包含真实模式所需的 `opencv-python`、`onnxruntime`、`Pillow`、`psutil`。真实称重（`weighing.mode: real`）还需在树莓派上额外安装 `RPi.GPIO`：

```bash
pip install RPi.GPIO
```

Mock 模式不依赖上述硬件相关库。

## 初始化数据库

```bash
python scripts/init_db.py
```

该命令会创建 `data/app.db`，创建 `products`、`transactions`、`calibration` 三张表，并插入默认商品和校准数据。

## 启动 GUI

```bash
python scripts/run_gui.py
```

也可以运行：

```bash
python main.py
```

GUI 启动后会自动进入等待称重状态，不需要点击“开始识别”。当前默认 `fullscreen: true`，会尝试铺满 7 寸 DSI 触摸屏；从 SSH 启动时会自动尝试使用本机显示 `:0`。点击界面右上角的“✕”可退出程序（全屏下也可先按 `Esc` 退出全屏）。

## 启动 API

```bash
python scripts/run_api.py
```

默认监听 `127.0.0.1:8000`，可访问：

```bash
curl http://127.0.0.1:8000/health
```

## Mock 模式说明

`config.yaml` 中三个 mode 独立控制：

| 模块            | 当前默认 | 说明                                                  |
| --------------- | -------- | ----------------------------------------------------- |
| `camera.mode`   | `real`   | 使用 USB 摄像头；切 `mock` 则用 MockCamera            |
| `vision.mode`   | `real`   | 使用 YOLO ONNX 推理；切 `mock` 则固定返回 apple       |
| `weighing.mode` | `real`   | 使用 HX711 称重（需先校准）；切 `mock` 则用 MockWeightSensor 模拟 |

Mock 模式用于在没有真实硬件时开发 GUI、数据库、计价和交易流程。

## 真实硬件/模型接入位置

- HX711 称重：`app/weighing/hx711_sensor.py`（**已实现**）
- 称重校准：`app/weighing/calibration.py`、`scripts/calibrate_scale.py`（**已实现**）
- USB 摄像头：`app/camera/usb_camera.py`（**已实现**）
- YOLO 模型：`app/vision/detector.py`（**已实现**）

## YOLO 识别引擎说明

识别接口定义在 `app/vision/yolo_interface.py`。`YOLODetector` 已完整实现：

- **模型文件**：`data/models/best.onnx`
- **标签映射**：`data/models/label_map.json`（65 类果蔬）
- **预处理**：保持宽高比缩放后 256x256 中心裁剪
- **推理**：ONNX Runtime CPU 推理，固定 3 线程
- **返回格式**：

```python
{"label": "apple_fuji", "confidence": 0.85, "zh_name": "红富士苹果"}
```

- **输入兼容**：同时支持 `np.ndarray`（内存直传）和 `str`（文件路径）
- **数据库同步**：`python scripts/sync_db.py` 将全部 65 类写入 `products` 表（默认单价 9.9 元/kg）
- **独立测速**：`python scripts/speed_test.py` 批量测试推理耗时

> 提示：`label` 字段用于数据库查价，`zh_name` 为 UI 显示中文名。默认价格可通过 API 或直接修改数据库更新。

## 称重校准脚本说明

```bash
python scripts/calibrate_scale.py
```

脚本已完整实现多点砝码校准：空载去皮 → 逐次放砝码采集 → 过原点线性回归计算 `scale_factor` → 写入 `calibration` 表 → 空载回零验证。详见 `docs/calibration.md`。

## 数据库表结构

- `products`：商品 label、中文名、单价。
- `transactions`：确认后的交易记录。只有 GUI 点击“确认”后才写入。
- `calibration`：HX711 校准参数。由 `scripts/calibrate_scale.py` 写入，`real` 模式下 `HX711Sensor` 启动时读取（GUI 不直接读写）。

## 常用命令

```bash
cd /home/pi/project/fruit_retail_system
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
python scripts/run_gui.py
python scripts/run_api.py
python scripts/calibrate_scale.py
python scripts/sync_db.py        # 同步 65 类果蔬到数据库
python scripts/speed_test.py     # 测试 YOLO 推理速度
python scripts/stream_test.py    # 测试 USB 摄像头实时流
python -m pytest
```
