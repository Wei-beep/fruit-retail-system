from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk  # 引入 PIL 用于渲染视频帧

from app.camera.camera_interface import Camera
from app.camera.mock_camera import MockCamera
from app.camera.usb_camera import USBCamera
from app.core.config import load_config
from app.core.constants import PROJECT_TITLE
from app.core.display import configure_gui_display
from app.db.init_db import initialize_database
from app.gui.gui_controller import GUIController
from app.gui.performance_monitor import PerformanceMonitor
from app.pricing.price_service import PriceService
from app.pricing.transaction_service import TransactionService
from app.vision.detector import YOLODetector
from app.vision.mock_detector import MockFruitVegetableDetector
from app.weighing.hx711_sensor import HX711Sensor
from app.weighing.mock_sensor import MockWeightSensor
from app.weighing.stability import StabilityDetector
from app.workflow.transaction_flow import TransactionFlow


class MainWindow:
    def __init__(self, root: tk.Tk, controller: GUIController, config: dict, camera: Camera) -> None:
        self.root = root
        self.controller = controller
        self.config = config
        self.camera = camera  # 注入摄像头实例用于拉取视频流
        self.fields: dict[str, tk.StringVar] = {
            "status": tk.StringVar(value="初始化..."),
            "name_cn": tk.StringVar(value="-"),
            "label": tk.StringVar(value="-"),
            "confidence": tk.StringVar(value="-"),
            "weight_kg": tk.StringVar(value="-"),
            "price_per_kg": tk.StringVar(value="-"),
            "total_price": tk.StringVar(value="-"),
        }
        self._build()

        # 性能监控：由 config.yaml 中 gui.monitor_performance 控制开关
        gui_config = config.get("gui", {})
        self._monitor = PerformanceMonitor()
        if gui_config.get("monitor_performance", False):
            self._monitor.start()
    def _build(self) -> None:
        gui_config = self.config["gui"]
        self.root.title(PROJECT_TITLE)
        self.root.geometry(f"{gui_config['width']}x{gui_config['height']}")
        self.root.resizable(False, False)
        # 窗口管理器关闭按钮也走统一退出逻辑
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if gui_config.get("fullscreen"):
            self.root.attributes("-fullscreen", True)
            self.root.bind("<Escape>", lambda _event: self.root.attributes("-fullscreen", False))

        # 稍微缩小外边距，给画面留出更多发挥空间
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        # === 核心修改 1：顶部 Header 区域（独占一行，解决长标题撑爆布局的问题） ===
        header_frame = ttk.Frame(container)
        header_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        # 右上角退出按钮：全屏无标题栏时也能退出程序（先 pack 以占据右侧）
        close_btn = tk.Button(
            header_frame,
            text="✕",
            font=("Arial", 14, "bold"),
            fg="white",
            bg="#c0392b",
            activebackground="#e74c3c",
            activeforeground="white",
            relief="flat",
            width=3,
            command=self._on_close,
        )
        close_btn.pack(side=tk.RIGHT, anchor="ne")

        title = ttk.Label(header_frame, text=PROJECT_TITLE, font=("Arial", 20, "bold"))
        title.pack(anchor="w")

        status = ttk.Label(header_frame, textvariable=self.fields["status"], font=("Arial", 16))
        status.pack(anchor="w", pady=(4, 0))

        # === 核心修改 2：底部主体区域（左右分栏） ===
        content_frame = ttk.Frame(container)
        content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # 左侧：数据表单和按钮（让它只占必须的宽度）
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        grid = ttk.Frame(left_panel)
        grid.pack(fill=tk.X)

        rows = [
            ("识别种类", "name_cn"),
            ("英文字段", "label"),
            ("置信度", "confidence"),
            ("重量 kg", "weight_kg"),
            ("单价 元/kg", "price_per_kg"),
            ("总价 元", "total_price"),
        ]
        for index, (label, key) in enumerate(rows):
            ttk.Label(grid, text=label, font=("Arial", 14)).grid(
                row=index, column=0, sticky="w", padx=(0, 16), pady=6
            )
            ttk.Label(grid, textvariable=self.fields[key], font=("Arial", 16, "bold")).grid(
                row=index, column=1, sticky="w", pady=6
            )

        buttons = ttk.Frame(left_panel)
        buttons.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        ttk.Button(buttons, text="确认", command=self.controller.confirm_current).pack(
            side=tk.LEFT, ipadx=36, ipady=12, padx=(0, 16)
        )
        ttk.Button(buttons, text="清除", command=self.controller.clear_current).pack(
            side=tk.LEFT, ipadx=36, ipady=12
        )

        # 右侧：视频流（毫无限制地霸占剩下的所有空间）
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.video_label = ttk.Label(right_panel, text="正在加载视频流...")
        self.video_label.pack(expand=True)

    def start_video_stream(self) -> None:
        """从摄像头拉取实时画面并刷新到 UI 的右侧区域"""
        frame = self.camera.get_stream_frame()
        if frame is not None:
            self._monitor.tick()
            # OpenCV (BGR) 转为 PIL 需要的 RGB 格式
            rgb_frame = frame[:, :, ::-1]
            img = Image.fromarray(rgb_frame)
            
            # 缩放画面以适应右半边屏幕
            img = img.resize((480, 360), Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img)
            
            self.video_label.imgtk = imgtk  # 防止被 Python 垃圾回收
            self.video_label.configure(image=imgtk, text="")
            
        # 维持 30 FPS 的刷新率
        self.root.after(33, self.start_video_stream)

    def set_status(self, message: str) -> None:
        self.root.after(0, lambda: self.fields["status"].set(message))

    def show_error(self, message: str) -> None:
        self.root.after(0, lambda: self.fields["status"].set(f"错误: {message}"))

    def show_transaction(self, transaction: dict) -> None:
        def update() -> None:
            self.fields["status"].set("待确认")
            self.fields["name_cn"].set(transaction["name_cn"])
            self.fields["label"].set(transaction["label"])
            self.fields["confidence"].set(f"{transaction['confidence']:.2f}")
            self.fields["weight_kg"].set(f"{transaction['weight_kg']:.3f}")
            self.fields["price_per_kg"].set(f"{transaction['price_per_kg']:.2f}")
            self.fields["total_price"].set(f"{transaction['total_price']:.2f}")

        self.root.after(0, update)

    def clear_fields(self) -> None:
        def update() -> None:
            for key in ("name_cn", "label", "confidence", "weight_kg", "price_per_kg", "total_price"):
                self.fields[key].set("-")

        self.root.after(0, update)

    def _on_close(self) -> None:
        """退出程序：停止后台线程并销毁窗口。

        业务线程与性能监控均为 daemon 线程，主循环结束后会随进程退出；
        摄像头与 GPIO 由各自的 __del__ 释放。
        """
        self.controller.stop()
        self._monitor.stop()
        self.root.destroy()


def create_transaction_flow(config: dict) -> TransactionFlow:
    camera_config = config["camera"]
    weighing_config = config["weighing"]
    vision_config = config["vision"]

    if camera_config["mode"] == "mock":
        camera = MockCamera(camera_config["test_image_dir"], camera_config["image_save_dir"])
    else:
        camera = USBCamera(
            camera_config["device_index"],
            camera_config["image_save_dir"],
            camera_config["width"],
            camera_config["height"],
        )

    if weighing_config["mode"] == "mock":
        weight_sensor = MockWeightSensor()
    else:
        weight_sensor = HX711Sensor(
            dout_pin=weighing_config["dout_pin"],
            sck_pin=weighing_config["sck_pin"],
            gain=weighing_config.get("gain", 128),
        )

    if vision_config["mode"] == "mock":
        detector = MockFruitVegetableDetector()
    else:
        detector = YOLODetector(vision_config["model_path"], vision_config["confidence_threshold"])

    return TransactionFlow(
        weight_sensor=weight_sensor,
        stability_detector=StabilityDetector(
            weighing_config["stable_window_size"],
            weighing_config["stable_threshold_kg"],
        ),
        camera=camera,
        detector=detector,
        price_service=PriceService(),
        transaction_service=TransactionService(),
        min_valid_weight_kg=weighing_config["min_valid_weight_kg"],
        max_valid_weight_kg=weighing_config["max_valid_weight_kg"],
    )


def run_gui() -> None:
    initialize_database()
    config = load_config()
    configure_gui_display(config["gui"])
    root = tk.Tk()
    window_holder: dict[str, MainWindow] = {}

    flow = create_transaction_flow(config)
    controller = GUIController(
        transaction_flow=flow,
        on_status=lambda message: window_holder["window"].set_status(message),
        on_transaction_ready=lambda transaction: window_holder["window"].show_transaction(transaction),
        on_error=lambda message: window_holder["window"].show_error(message),
        on_cleared=lambda: window_holder["window"].clear_fields(),
    )
    
    # 挂载摄像头到主界面
    window = MainWindow(root, controller, config, camera=flow.camera)
    window_holder["window"] = window
    
    # 启动视频刷新守护循环
    window.start_video_stream()
    
    root.after(200, controller.start_waiting)
    root.mainloop()