"""YOLO11 检测模型测速脚本。

直接复用生产管线 app.vision.detector.YOLODetector（letterbox 640 + NMS），
对 data/images/test 下所有图片逐张计时 predict()，输出主类别/中文名/计数/置信度与耗时。
单一管线来源，避免与生产代码漂移。
"""
import _bootstrap  # noqa: F401

import os
import time

from app.core.config import load_config, resolve_project_path
from app.vision.detector import YOLODetector


def run_test() -> None:
    config = load_config()
    vision = config["vision"]
    test_dir = resolve_project_path(config["camera"]["test_image_dir"])

    detector = YOLODetector(vision["model_path"], vision["confidence_threshold"])

    if not test_dir.exists():
        print(f"未找到测试目标: {test_dir}，请检查路径。")
        return

    files = [
        str(test_dir / f)
        for f in sorted(os.listdir(test_dir))
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    if not files:
        print(f"测试目录无图片: {test_dir}")
        return

    # 预热：芯片首次矩阵计算内存分配较慢，先跑一次不计入成绩。
    print("🔥 引擎预热中...")
    detector.predict(files[0])

    print("\n🚀 开始批量测速...")
    total_time = 0.0
    valid_count = 0
    for f_path in files:
        start = time.time()
        res = detector.predict(f_path)
        elapsed_ms = (time.time() - start) * 1000
        print(
            f"图片: {os.path.basename(f_path):<22} | 识别: {res.get('zh_name', '—'):<10} "
            f"| 计数: {res.get('count', 0):<2} | 置信度: {res['confidence']:.1%} | 耗时: {elapsed_ms:.1f} ms"
        )
        total_time += elapsed_ms
        valid_count += 1

    avg_time = total_time / valid_count
    fps = 1000 / avg_time if avg_time > 0 else 0.0
    print("\n" + "=" * 40)
    print(f"📊 【最终测速报告 - {vision['model_path']}】")
    print(f"平均单张端到端耗时: {avg_time:.1f} ms")
    print(f"等效实时帧率: {fps:.1f} FPS")
    print("=" * 40)


if __name__ == "__main__":
    run_test()
