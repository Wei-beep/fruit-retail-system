import cv2
import numpy as np
import onnxruntime as ort
import json
import os
from app.vision.yolo_interface import FruitVegetableDetector

class YOLODetector(FruitVegetableDetector):
    """
    基于 ONNXRuntime 的真实果蔬识别引擎
    """
    def __init__(self, model_path: str, confidence_threshold: float = 0.5, label_path: str = 'data/models/label_map.json') -> None:
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.label_path = label_path

        # 1. 动态解析项目绝对路径
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        abs_model_path = os.path.join(base_dir, self.model_path)
        abs_label_path = os.path.join(base_dir, self.label_path)

        # 2. 加载类别字典
        if not os.path.exists(abs_label_path):
            raise FileNotFoundError(f"找不到字典文件: {abs_label_path}")
        with open(abs_label_path, 'r', encoding='utf-8') as f:
            self.label_map = json.load(f)
            
        if not os.path.exists(abs_model_path):
            raise FileNotFoundError(f"找不到模型文件: {abs_model_path}")

        # 3. 锁死 3 线程
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 3
        sess_options.inter_op_num_threads = 1 
        
        # 加载 ONNX 推理引擎
        self.session = ort.InferenceSession(abs_model_path, sess_options=sess_options, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        print(f"✅ 真实 YOLO 识别引擎加载完毕！(限制 3 线程, 模型: {self.model_path}, 阈值: {self.confidence_threshold})")

    def predict(self, image_input) -> dict:
        """
        兼容型接口：既能接收图片路径(str)，也能接收内存图片矩阵(numpy.ndarray)
        """
        try:
            # --- 1. 智能数据接入层 ---
            if isinstance(image_input, str):
                # 队友目前的设计：传进来的是硬盘路径
                if not os.path.exists(image_input):
                    print(f"⚠️ 图片路径不存在: {image_input}")
                    return {"label": "unknown", "confidence": 0.0}
                frame = cv2.imread(image_input)
            elif isinstance(image_input, np.ndarray):
                # 未来的终极形态：队友直接传内存矩阵 (内存直传)
                frame = image_input
            else:
                print("⚠️ 不支持的输入格式")
                return {"label": "unknown", "confidence": 0.0}

            if frame is None:
                return {"label": "unknown", "confidence": 0.0}

            # --- 2. 核心预处理  ---
            h, w = frame.shape[:2]
            imgsz = 256
            scale = imgsz / min(h, w)
            new_h, new_w = int(h * scale), int(w * scale)
            resized = cv2.resize(frame, (new_w, new_h))
            
            start_x = (new_w - imgsz) // 2
            start_y = (new_h - imgsz) // 2
            cropped = resized[start_y:start_y+imgsz, start_x:start_x+imgsz]
            
            img_data = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            input_tensor = np.expand_dims(np.transpose(img_data, (2, 0, 1)), axis=0)

            # --- 3. 矩阵推理 ---
            outputs = self.session.run(None, {self.input_name: input_tensor})
            
            # --- 4. 结果解析 ---
            probs = outputs[0][0]
            idx = int(np.argmax(probs))
            confidence = float(probs[idx])

            # 提取英文标签
            label_info = self.label_map.get(str(idx), {"en": "unknown", "zh": "未知"})
            english_label = label_info["en"]

            # top-3 候选：供前端低置信兜底时让顾客手动选择
            top_idx = [int(i) for i in np.argsort(probs)[-3:][::-1]]
            candidates = []
            for ci in top_idx:
                info = self.label_map.get(str(ci), {"en": "unknown", "zh": "未知"})
                candidates.append(
                    {"label": info["en"], "zh_name": info["zh"], "confidence": float(probs[ci])}
                )

            # 过滤低置信度（可选）
            if confidence < self.confidence_threshold:
                return {
                    "label": "unknown",
                    "confidence": confidence,
                    "zh_name": "置信度过低",
                    "candidates": candidates,
                }

            # --- 4. 返回契约字典 ---
            return {
                "label": english_label,  # 队友拿这个去数据库查价格
                "confidence": confidence,
                "zh_name": label_info["zh"], # 额外塞入中文名，如果他的 UI 想直接显示中文就能用到
                "candidates": candidates,
            }
            
        except Exception as e:
            print(f"⚠️ YOLO 推理出错: {e}")
            return {"label": "error", "confidence": 0.0}