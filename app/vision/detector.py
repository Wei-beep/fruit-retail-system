import cv2
import numpy as np
import onnxruntime as ort
import json
import os
from app.vision.yolo_interface import FruitVegetableDetector


class YOLODetector(FruitVegetableDetector):
    """基于 ONNXRuntime 的真实果蔬识别引擎（YOLO11 目标检测模型）。

    输入 [1,3,640,640]（RGB、/255、letterbox 保宽高比），输出 [1,4+N,8400]
    （前 4 为 xc,yc,w,h，后 N 为各类别置信度）。经 NMS 过滤重叠框后，
    按检出物体聚合为单一主类别 + 计数，返回契约：
        {label, confidence, zh_name, count, candidates, detected_labels}
    其中 candidates 为置信度前三的不同类别，供 Web 低置信兜底/混放手动选品。
    """

    INPUT_SIZE = 640  # 模型固定输入边长

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.5,
        label_path: str = 'data/models/label_map.json',
        score_threshold: float = 0.25,
        mixed_score_threshold: float = 0.05,
        nms_threshold: float = 0.45,
    ) -> None:
        self.model_path = model_path
        # confidence_threshold：最终「可信」门槛——主检测低于此值则判 unknown，
        #   交由 Web 低置信兜底/手动选品（沿用旧分类模型的语义）。
        self.confidence_threshold = confidence_threshold
        # score_threshold / nms_threshold：检测后处理内部参数（README 建议 0.25 / 0.45）。
        self.score_threshold = score_threshold
        # mixed_score_threshold：只用于“是否存在其它类别”的低阈值检查。
        # 它不参与主类别计价，只让小件低置信混放也能触发多类别提示。
        self.mixed_score_threshold = mixed_score_threshold
        self.nms_threshold = nms_threshold
        self.label_path = label_path

        # 1. 动态解析项目绝对路径
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        abs_model_path = os.path.join(base_dir, self.model_path)
        abs_label_path = os.path.join(base_dir, self.label_path)

        # 2. 加载类别字典（新格式：{"0": {"label": ..., "zh_name": ...}}）
        if not os.path.exists(abs_label_path):
            raise FileNotFoundError(f"找不到字典文件: {abs_label_path}")
        with open(abs_label_path, 'r', encoding='utf-8') as f:
            self.label_map = json.load(f)

        if not os.path.exists(abs_model_path):
            raise FileNotFoundError(f"找不到模型文件: {abs_model_path}")

        # 3. 锁死 3 线程（640 检测计算量大于旧分类模型，README 建议 2~3 线程）
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 3
        sess_options.inter_op_num_threads = 1

        # 加载 ONNX 推理引擎
        self.session = ort.InferenceSession(
            abs_model_path, sess_options=sess_options, providers=['CPUExecutionProvider']
        )
        self.input_name = self.session.get_inputs()[0].name
        print(
            f"✅ 真实 YOLO11 检测引擎加载完毕！(限制 3 线程, 模型: {self.model_path}, "
            f"可信阈值: {self.confidence_threshold}, score: {self.score_threshold}, "
            f"mixed_score: {self.mixed_score_threshold}, nms: {self.nms_threshold})"
        )

    def _label_info(self, class_id: int) -> dict:
        return self.label_map.get(str(class_id), {"label": "unknown", "zh_name": "未知"})

    def _aggregate_by_label(self, class_ids: np.ndarray, scores: np.ndarray) -> dict[str, dict]:
        per_label: dict[str, dict] = {}
        for cid, sc in zip(class_ids.tolist(), scores.tolist()):
            info = self._label_info(int(cid))
            label = info["label"]
            sc = float(sc)
            entry = per_label.get(label)
            if entry is None:
                per_label[label] = {"zh_name": info["zh_name"], "max_conf": sc, "count": 1}
            else:
                entry["count"] += 1
                if sc > entry["max_conf"]:
                    entry["max_conf"] = sc
        return per_label

    @staticmethod
    def _label_list(per_label: dict[str, dict]) -> list[dict]:
        return [
            {"label": lb, "zh_name": e["zh_name"], "confidence": e["max_conf"], "count": e["count"]}
            for lb, e in sorted(per_label.items(), key=lambda kv: kv[1]["max_conf"], reverse=True)
        ]

    @staticmethod
    def _letterbox(frame: np.ndarray, size: int) -> np.ndarray:
        """保持宽高比缩放到 size×size，不足部分以 114 灰边填充（YOLO 标准 letterbox）。"""
        h, w = frame.shape[:2]
        scale = size / max(h, w)
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((size, size, 3), 114, dtype=frame.dtype)
        top = (size - new_h) // 2
        left = (size - new_w) // 2
        canvas[top:top + new_h, left:left + new_w] = resized
        return canvas

    def predict(self, image_input) -> dict:
        """兼容型接口：既能接收图片路径(str)，也能接收内存图片矩阵(numpy.ndarray)。"""
        try:
            # --- 1. 智能数据接入层 ---
            if isinstance(image_input, str):
                if not os.path.exists(image_input):
                    print(f"⚠️ 图片路径不存在: {image_input}")
                    return {"label": "unknown", "confidence": 0.0, "zh_name": "未知", "count": 0, "candidates": [], "detected_labels": []}
                frame = cv2.imread(image_input)
            elif isinstance(image_input, np.ndarray):
                frame = image_input
            else:
                print("⚠️ 不支持的输入格式")
                return {"label": "unknown", "confidence": 0.0, "zh_name": "未知", "count": 0, "candidates": [], "detected_labels": []}

            if frame is None:
                return {"label": "unknown", "confidence": 0.0, "zh_name": "未知", "count": 0, "candidates": [], "detected_labels": []}

            # --- 2. 核心预处理：letterbox 到 640×640，BGR→RGB，/255，CHW ---
            letterboxed = self._letterbox(frame, self.INPUT_SIZE)
            img_data = cv2.cvtColor(letterboxed, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            input_tensor = np.expand_dims(np.transpose(img_data, (2, 0, 1)), axis=0)

            # --- 3. 矩阵推理 ---
            outputs = self.session.run(None, {self.input_name: input_tensor})

            # --- 4. 后处理：解析 [1,4+N,8400] → 候选筛选 → NMS ---
            # 转置为 [8400, 4+N]：每行前 4 为框(xc,yc,w,h)，后 N 为各类别得分
            preds = np.squeeze(outputs[0], axis=0).T  # (8400, 4+N)
            class_scores = preds[:, 4:]
            class_ids = np.argmax(class_scores, axis=1)
            scores = class_scores[np.arange(class_scores.shape[0]), class_ids]

            # 低阈值混放扫描：只用于 detected_labels，不影响主识别计价。
            # 目的：多个李子里混入一个番茄时，番茄即使置信度偏低也能触发多类别提示。
            detected_labels = []
            mixed_keep = scores > self.mixed_score_threshold
            if np.any(mixed_keep):
                mixed_boxes_xywh = preds[mixed_keep, :4]
                mixed_scores = scores[mixed_keep]
                mixed_class_ids = class_ids[mixed_keep]
                mixed_xy = mixed_boxes_xywh[:, :2] - mixed_boxes_xywh[:, 2:] / 2.0
                mixed_nms_boxes = np.concatenate([mixed_xy, mixed_boxes_xywh[:, 2:]], axis=1).tolist()
                mixed_indices = cv2.dnn.NMSBoxes(
                    mixed_nms_boxes,
                    mixed_scores.tolist(),
                    self.mixed_score_threshold,
                    self.nms_threshold,
                )
                if mixed_indices is not None and len(mixed_indices) > 0:
                    mixed_indices = np.array(mixed_indices).flatten()
                    mixed_per_label = self._aggregate_by_label(
                        mixed_class_ids[mixed_indices],
                        mixed_scores[mixed_indices],
                    )
                    detected_labels = self._label_list(mixed_per_label)

            keep = scores > self.score_threshold
            if not np.any(keep):
                confidence = float(detected_labels[0]["confidence"]) if detected_labels else 0.0
                count = int(detected_labels[0]["count"]) if detected_labels else 0
                return {
                    "label": "unknown",
                    "confidence": confidence,
                    "zh_name": "未知",
                    "count": count,
                    "candidates": detected_labels[:3],
                    "detected_labels": detected_labels,
                }

            boxes_xywh = preds[keep, :4]
            scores_kept = scores[keep]
            class_ids_kept = class_ids[keep]

            # 中心点 xywh → 左上角 xywh（NMS 在模型输出坐标系内进行，无需还原原图，因为不返回框）
            xy = boxes_xywh[:, :2] - boxes_xywh[:, 2:] / 2.0
            nms_boxes = np.concatenate([xy, boxes_xywh[:, 2:]], axis=1).tolist()

            indices = cv2.dnn.NMSBoxes(
                nms_boxes, scores_kept.tolist(), self.score_threshold, self.nms_threshold
            )
            if indices is None or len(indices) == 0:
                confidence = float(detected_labels[0]["confidence"]) if detected_labels else 0.0
                count = int(detected_labels[0]["count"]) if detected_labels else 0
                return {
                    "label": "unknown",
                    "confidence": confidence,
                    "zh_name": "未知",
                    "count": count,
                    "candidates": detected_labels[:3],
                    "detected_labels": detected_labels,
                }
            indices = np.array(indices).flatten()

            final_class_ids = class_ids_kept[indices]
            final_scores = scores_kept[indices]

            # --- 5. 聚合：按「解析后的 label」统计计数与最高置信度（而非 class_id）---
            # label_map 中存在同一 label 对应多个 class_id 的情况（如 banana_yellow=14/49/53、
            # apple_red_delicious=4/33 等 6 个 label）。若按 class_id 聚合会把同一物种拆成多类，
            # 导致 count 少算、candidates 出现重复项并挤掉真实的第三候选，故必须按 label 归并。
            per_label = self._aggregate_by_label(final_class_ids, final_scores)

            # 主类别 = 最高单框置信度所在的 label；count = 该 label 的检出框总数
            primary_label, primary_entry = max(per_label.items(), key=lambda kv: kv[1]["max_conf"])
            primary_conf = primary_entry["max_conf"]
            primary_count = primary_entry["count"]
            primary_zh = primary_entry["zh_name"]

            # candidates：按 label 最高置信度取前三个不同 label（已按 label 去重）
            top_labels = sorted(per_label.items(), key=lambda kv: kv[1]["max_conf"], reverse=True)[:3]
            candidates = self._label_list(dict(top_labels))
            if not detected_labels:
                detected_labels = self._label_list(per_label)

            # --- 6. 可信门槛：主检测低于阈值则判 unknown，转候选/手动选品 ---
            if primary_conf < self.confidence_threshold:
                return {
                    "label": "unknown",
                    "confidence": primary_conf,
                    "zh_name": "置信度过低",
                    "count": primary_count,
                    "candidates": candidates,
                    "detected_labels": detected_labels,
                }

            # --- 7. 返回契约字典 ---
            return {
                "label": primary_label,  # 业务层据此查价
                "confidence": primary_conf,
                "zh_name": primary_zh,
                "count": primary_count,  # 秤盘上该类果蔬检出个数（供重数比异常校验）
                "candidates": candidates,
                "detected_labels": detected_labels,
            }

        except Exception as e:
            print(f"⚠️ YOLO 推理出错: {e}")
            return {"label": "error", "confidence": 0.0, "zh_name": "未知", "count": 0, "candidates": [], "detected_labels": []}
