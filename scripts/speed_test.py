import cv2
import numpy as np
import onnxruntime as ort
import json
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class FreshTester:
    def __init__(self, model_path, label_path):
        with open(label_path, 'r', encoding='utf-8') as f:
            self.label_map = json.load(f)
        
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 3
        
        self.session = ort.InferenceSession(model_path, sess_options=sess_options, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        print(f"--- 成功加载模型: {model_path} ---")

    def predict_file(self, image_path):
        frame = cv2.imread(image_path)
        if frame is None: return None

        # --- 预处理逻辑 ---
        h, w = frame.shape[:2]
        imgsz = 256
        scale = imgsz / min(h, w)
        new_h, new_w = int(h * scale), int(w * scale)
        resized = cv2.resize(frame, (new_w, new_h))
        start_x = (new_w - imgsz) // 2
        start_y = (new_h - imgsz) // 2
        cropped = resized[start_y:start_y+imgsz, start_x:start_x+imgsz]
        
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        img_data = rgb.astype(np.float32) / 255.0
        img_data = np.transpose(img_data, (2, 0, 1))
        input_tensor = np.expand_dims(img_data, axis=0)

        # --- 核心推理与计时 ---
        start_time = time.time()
        outputs = self.session.run(None, {self.input_name: input_tensor})
        infer_time = time.time() - start_time
        
        # --- 解析 ---
        probs = outputs[0][0]
        idx = int(np.argmax(probs))
        confidence = probs[idx]
        
        return {
            "zh": self.label_map[str(idx)]['zh'],
            "conf": confidence,
            "time_ms": infer_time * 1000 # 转换为毫秒
        }

def run_test():
    MODEL_FILE = str(PROJECT_ROOT / 'data' / 'models' / 'best.onnx')
    LABEL_FILE = str(PROJECT_ROOT / 'data' / 'models' / 'label_map.json')
    TEST_TARGET = str(PROJECT_ROOT / 'data' / 'images' / 'test') 

    tester = FreshTester(MODEL_FILE, LABEL_FILE)

    if not os.path.exists(TEST_TARGET):
        print(f"未找到测试目标: {TEST_TARGET}，请检查路径。")
        return

    files = [os.path.join(TEST_TARGET, f) for f in os.listdir(TEST_TARGET) 
             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    # --- 预热阶段 ---
    # 芯片刚开始运行矩阵计算时，内存分配会很慢。先跑一次不计入成绩。
    print("🔥 引擎预热中...")
    if files:
        tester.predict_file(files[0])

    # --- 正式测速阶段 ---
    print(f"\n🚀 开始批量测速...")
    total_time = 0
    valid_count = 0

    for f_path in files:
        res = tester.predict_file(f_path)
        if res:
            print(f"图片: {os.path.basename(f_path):<15} | 识别: {res['zh']:<8} | 置信度: {res['conf']:.1%} | 耗时: {res['time_ms']:.1f} ms")
            total_time += res['time_ms']
            valid_count += 1

    if valid_count > 0:
        avg_time = total_time / valid_count
        fps = 1000 / avg_time
        print("\n" + "="*40)
        print(f"📊 【最终测速报告 - {MODEL_FILE}】")
        print(f"平均单张推理耗时: {avg_time:.1f} ms")
        print(f"等效实时帧率: {fps:.1f} FPS")
        print("="*40)

if __name__ == "__main__":
    run_test()