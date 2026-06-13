# Mock 模式

Mock 模式用于在没有真实摄像头、HX711 称重模块和 YOLO 模型时验证核心业务闭环。当前默认配置已切换为 `real`（`config.yaml` 中 camera、vision、weighing 均为真实硬件），Mock 模式作为开发/调试备选保留，将对应模块的 `mode` 改回 `mock` 即可启用。

## MockWeightSensor

`app/weighing/mock_sensor.py` 中的 `MockWeightSensor` 返回一组逐渐稳定的重量读数。读数从 0.50 kg 附近变化，最终稳定在约 0.52 kg，并在数据读完后继续返回 0.52 kg 附近的小幅波动值。

## StabilityDetector

`StabilityDetector` 维护固定长度滑动窗口。当窗口填满且最大值与最小值差值不超过阈值时，认为重量稳定。默认配置为窗口 10、阈值 0.01 kg（见 `config.yaml` 的 `weighing.stable_window_size` / `stable_threshold_kg`）。

## MockCamera

`app/camera/mock_camera.py` 已适配内存直传，`capture()` 返回 `np.ndarray`（不再落盘）。它先查找 `data/images/test/` 下的 jpg、jpeg 或 png 图片（当前目录内已有 4 张 PNG 测试图），动态导入 cv2 解码为 BGR 矩阵返回；如果找不到图片或环境未安装 OpenCV，则返回一张 640×480 全黑 `np.zeros` 矩阵，保证流程可以继续。`get_stream_frame()` 同样返回全黑占位帧，供 GUI 视频流使用。

## MockFruitVegetableDetector

`app/vision/mock_detector.py` 固定返回：

```python
{"label": "apple", "confidence": 0.97}
```

系统随后从 `products` 表查询 `apple` 的中文名和单价。

## 使用原因

Mock 模式让 GUI、数据库、计价和交易确认流程可以先稳定下来，避免硬件调试和模型训练阻塞业务开发。

## 对后续开发的帮助

只要真实模块遵守现有接口，后续可逐步替换 Mock 摄像头、Mock 称重和 Mock 识别器，而不需要重写 GUI 或交易流程。
