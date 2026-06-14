"""HX711 称重传感器全屏 GUI 实时显示脚本

在全屏窗口上实时显示当前重量，最小精度 1g（舍弃小数点后数据，不足 1g 直接截断）。
参考 scripts/weighing_test.py，直接驱动真实 HX711Sensor，必须先运行
scripts/calibrate_scale.py 完成校准，否则读数没有物理意义。

读数在 Tk 主线程内用 root.after 轮询（单次读取、直接显示，不开后台线程）。
偶发的“820g 跳变”根因已确认是 HX711 的退化读数（raw=-1，DOUT 卡在全 1），
已在 app/weighing/hx711_sensor.py 的 _read_raw() 里统一重读剔除，此处无需再过滤。

用法：
  python scripts/weighing_test_gui.py
  按 Esc（或点右上角 ✕）退出。
"""
import _bootstrap  # noqa: F401

import sys
import tkinter as tk

from app.core.config import load_config
from app.core.display import configure_gui_display
from app.weighing.hx711_sensor import HX711Sensor


# 刷新间隔（毫秒）。读数在主线程内完成，间隔之间把控制权交还 Tk 事件循环。
REFRESH_MS = 150


class WeighingDisplay:
    """全屏显示当前重量（整数克）的简易测试窗口。"""

    def __init__(self, root: tk.Tk, sensor: HX711Sensor) -> None:
        self.root = root
        self.sensor = sensor
        self._running = True

        self.root.title("HX711 称重实时显示")
        self.root.configure(bg="white")
        self.root.attributes("-fullscreen", True)
        # 全屏无标题栏，提供 Esc / 窗口关闭 / ✕ 三个退出入口
        self.root.bind("<Escape>", lambda _event: self._on_close())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.weight_var = tk.StringVar(value="-- g")
        # 重量大字，水平垂直居中
        tk.Label(
            self.root,
            textvariable=self.weight_var,
            font=("Arial", 130, "bold"),
            fg="black",
            bg="white",
        ).pack(expand=True)

        tk.Label(
            self.root,
            text="按 Esc 退出",
            font=("Arial", 16),
            fg="#888888",
            bg="white",
        ).pack(side=tk.BOTTOM, pady=12)

        close_btn = tk.Button(
            self.root,
            text="✕",
            font=("Arial", 18, "bold"),
            fg="white",
            bg="#c0392b",
            activebackground="#e74c3c",
            activeforeground="white",
            relief="flat",
            width=3,
            command=self._on_close,
        )
        close_btn.place(relx=1.0, x=-10, y=10, anchor="ne")

        # 主线程内轮询读数（不开后台线程）
        self.root.after(REFRESH_MS, self._tick)

    def _tick(self) -> None:
        if not self._running:
            return
        try:
            weight_kg = self.sensor.read_weight()  # 驱动已自动剔除退化读数
            text = f"{int(weight_kg * 1000)} g"     # 舍弃小数点后数据（向零截断到整数克）
        except Exception as exc:  # 读数异常时显示提示而不是崩溃
            text = "读数异常"
            print(f"❌ 读数异常: {exc}")
        self.weight_var.set(text)
        self.root.after(REFRESH_MS, self._tick)

    def _on_close(self) -> None:
        self._running = False
        self.root.destroy()


def main() -> None:
    config = load_config()
    wc = config["weighing"]

    print(f"🔌 初始化 HX711（DT=GPIO{wc['dout_pin']}, SCK=GPIO{wc['sck_pin']}）...")
    try:
        sensor = HX711Sensor(
            dout_pin=wc["dout_pin"],
            sck_pin=wc["sck_pin"],
            gain=wc.get("gain", 128),
        )
    except Exception as exc:
        print(f"❌ 传感器初始化失败: {exc}")
        print("   请检查接线，或确认已在树莓派上运行并完成校准。")
        sys.exit(1)
    print("✅ 传感器就绪，启动全屏显示（Esc 退出）...")

    # 从 SSH 启动时自动指向树莓派本机显示 :0（与主 GUI 一致）
    configure_gui_display(config["gui"])

    root = tk.Tk()
    WeighingDisplay(root, sensor)
    root.mainloop()


if __name__ == "__main__":
    main()
