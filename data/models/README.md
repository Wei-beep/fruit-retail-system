# YOLO 模型目录

当前 `best.onnx` 为 **YOLO11n 目标检测模型**（66 类果蔬，输入 `[1,3,640,640]`、输出 `[1,70,8400]`），由 `app/vision/detector.py` 的 `YOLODetector` 加载（letterbox 640 预处理 + `cv2.dnn.NMSBoxes` 后处理 + 按类别聚合计数）。

文件说明：

- `best.onnx`：当前生产用 YOLO11 检测模型。
- `label_map.json`：66 类中英文映射（`{"<id>": {"label": ..., "zh_name": ...}}`），`detector.py` 与 `scripts/sync_db.py` 共用，顺序以项目根目录 `data.yaml` 的 `names` 为准。
- `best_classify_legacy.onnx`：旧版**分类模型**（65 类、256×256 中心裁剪 + argmax），仅作回退保留，不再被加载。
- `best.pt` / `best_int8.onnx`：旧分类模型的其它格式产物，遗留保留。

`*.onnx` / `*.pt` 体积大、不入 git（见 `.gitignore`），单独分发；`label_map.json`、本 README 入库。Mock 模式不加载任何模型。
