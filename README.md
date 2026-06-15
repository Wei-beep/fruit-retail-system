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
- `HX711Sensor` 已完成：RPi.GPIO 位操作读取 24 位 ADC，结合 `calibration` 表参数换算 kg，支持去皮、中位数采样和电源管理。
- `StabilityDetector` 使用滑动窗口判断重量稳定。
- Mock 组件保留作为开发/调试备选：`MockWeightSensor`（约 0.52 kg）、`MockCamera`（测试图）、`MockFruitVegetableDetector`（固定 `apple` 0.97），详见 `docs/mock_mode.md`。
- SQLite `products` 表支持 65 类果蔬价格（通过 `scripts/sync_db.py` 同步）。
- 两套前端共用业务层，由 `gui.frontend` 切换：默认 Web kiosk（`app/web`，FastAPI + 原生静态页，WebSocket 实时态 + MJPEG 视频 + 低置信候选/品类手动选品 + 扫码支付占位），保留旧 Tkinter（`app/gui`）。
- 自动等待称重、识别、计价并显示待确认交易；确认后写入 `transactions` 表，取消则丢弃当前待确认交易。
- FastAPI 对外预留服务结构（`app/api`），`GET /health` 可用，价格/交易接口已实现。

## 业务流程（Web kiosk）

完整交易闭环由 `TransactionFlow` + `GUIController` 编排，前端按状态机渲染：

1. **放置 / 空闲**：秤面重量低于触发阈值（`weighing.trigger_threshold_kg`，默认 20g）时视为空秤，界面只显示醒目的「请将商品放到秤上」引导、**不显示克重**；超过阈值后才切到实时克重显示。仅被碰一下（触发但未进入稳定）**不会**触发识别。
2. **识别**：重量进入稳定窗口（`StabilityDetector`）后，抓拍一帧喂给 YOLO，进入「识别中」。整条链路里 YOLO 推理**只在此刻发生一次**，空闲 / 称重 / 支付阶段不占 CPU（`detector.predict()` 仅由 `prepare_transaction` 在稳定后调用）。
3. **确认**：展示品名、置信度、重量、单价、总价。低置信 / 未登记商品不报错，给出 top-3 候选，并可进入全屏品类选择器手动选品（按当前重量重新计价）。点「确认」才写入 `transactions` 表，点「取消」丢弃当前待确认交易。
4. **支付**：确认后进入扫码支付引导（二维码为占位图，非真实支付）。点「完成」回到空闲。
5. **取走再开始**：点「完成」后**不会立刻**进入下一轮——后端先等秤面重量回落到触发阈值以下（上一件商品被取走）再开始下一轮称重识别，避免商品仍在秤上时被重复识别（带 10s 兜底超时，见 `TransactionFlow.wait_for_release`）。

界面右上角有「中 / EN」分段开关，可**纯前端热切换**全站中英文（默认中文；仅在放置-识别-确认主界面显示，支付 / 品类选择器全屏遮罩时不显示）。

## 当前未实现/简化的部分

- FastAPI 业务接口：`app/api/` 仅提供基础实现，鉴权、完整校验、分页和设备状态待补充
- 复杂 UI 美化和完整自动化测试体系

## 技术栈

- Python 3
- SQLite，使用标准库 `sqlite3`
- 前端：默认 Chromium kiosk Web 前端（FastAPI + WebSocket + MJPEG，原生 HTML/CSS/JS），保留 Tkinter（800x480，面向 DSI 7 寸触摸屏）
- YAML 配置，使用 `pyyaml`
- FastAPI + uvicorn：`app/web` Web 前端后端（WS 依赖 `websockets`）、`app/api` 对外预留
- pytest 基础测试（Web 层测试依赖 `httpx`）
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
app/workflow    交易流程编排 + 组装工厂(create_transaction_flow)
app/gui         Tkinter 界面和控制器（前端之一，含实时视频流）
app/web         默认 Web kiosk 前端(FastAPI + 原生静态页，WS/MJPEG/品类接口)
app/api         FastAPI 对外预留服务和路由
scripts         初始化、运行 GUI/Web/API、校准、拍照、测速、同步等脚本
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

## 启动前端

前端有两套，由 `config.yaml` 的 `gui.frontend` 切换：默认 `web`（Chromium kiosk），保留 `tk`（旧 Tkinter）。`python main.py` 按该配置分发。

```bash
python main.py            # 按 gui.frontend 启动默认前端(web)
python scripts/run_web.py # 直接启动 Web kiosk
python scripts/run_gui.py # 启动旧 Tkinter 前端
```

**Web 前端（默认）**：浅色超市风触摸界面，`run_web()` 进程内起 uvicorn 并用 Chromium kiosk 全屏打开本地页面。调试时设 `gui.launch_browser: false`，再手动用浏览器打开 `http://127.0.0.1:8000`；访问 `/?demo=1` 可无硬件走查全部界面状态。协议与状态详见 `docs/web_frontend.md`。

**Tkinter 前端**：自动进入等待称重状态，无需点击“开始识别”。默认 `fullscreen: true` 铺满 7 寸 DSI 触摸屏；从 SSH 启动时自动尝试使用本机显示 `:0`。右上角“✕”退出（全屏下可先按 `Esc`）。

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

## YOLO 识别引擎说明

识别接口定义在 `app/vision/yolo_interface.py`。`YOLODetector` 已完整实现：

- **模型文件**：`data/models/best.onnx`
- **标签映射**：`data/models/label_map.json`（65 类果蔬）
- **预处理**：保持宽高比缩放后 256x256 中心裁剪
- **推理**：ONNX Runtime CPU 推理，固定 3 线程
- **返回格式**：

```python
{"label": "apple_fuji", "confidence": 0.85, "zh_name": "红富士苹果",
 "candidates": [  # top-3，供前端低置信兜底时让顾客手动选择
   {"label": "apple_fuji", "zh_name": "红富士苹果", "confidence": 0.85},
   {"label": "apple_granny", "zh_name": "青苹果", "confidence": 0.10},
   {"label": "pear", "zh_name": "梨", "confidence": 0.03}]}
```

- **低置信处理**：置信度低于阈值（`vision.confidence_threshold`）时 `label` 返回 `unknown`，不报错；Web 前端据 `candidates` 让顾客手动选品，Tk 前端忽略 `candidates`
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
python main.py                # 默认 Web kiosk 前端
python scripts/run_web.py     # 直接启动 Web kiosk 前端
python scripts/run_gui.py     # 旧 Tkinter 前端
python scripts/run_api.py
python scripts/calibrate_scale.py
python scripts/sync_db.py        # 同步 65 类果蔬到数据库
python scripts/speed_test.py     # 测试 YOLO 推理速度
python scripts/stream_test.py    # 测试 USB 摄像头实时流
python scripts/weighing_test_gui.py  # 全屏实时显示称重（整数克）
python -m pytest
```
