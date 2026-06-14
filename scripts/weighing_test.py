"""HX711 称重传感器快速验证脚本

检查传感器是否正常通信、显示实时原始值和换算后的重量。
必须先运行 calibrate_scale.py 完成校准，否则使用默认参数 (offset=0, scale=1)。
"""
import _bootstrap  # noqa: F401

import sys
import time

from app.core.config import load_config
from app.weighing.hx711_sensor import HX711Sensor


def main() -> None:
    config = load_config()
    wc = config["weighing"]

    print("=" * 50)
    print("🍎  HX711 称重传感器验证")
    print("=" * 50)
    print(f"\n🔌 初始化（DT=GPIO{wc['dout_pin']}, SCK=GPIO{wc['sck_pin']}）...")

    try:
        sensor = HX711Sensor(
            dout_pin=wc["dout_pin"],
            sck_pin=wc["sck_pin"],
            gain=wc.get("gain", 128),
        )
    except Exception as e:
        print(f"❌ 失败: {e}")
        sys.exit(1)

    print("✅ 传感器就绪！")
    print("-" * 50)
    print("实时读数（Ctrl+C 退出）：")
    print(f"{'原始值':>10} | {'重量(kg)':>10}")
    print("-" * 50)

    try:
        while True:
            raw = sensor.read_raw_median(3)
            weight = sensor.read_weight()
            print(f"{raw:>10.1f} | {weight:>10.4f}")
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n\n✅ 测试结束。")
    except Exception as e:
        print(f"\n❌ 读数异常: {e}")


if __name__ == "__main__":
    main()
