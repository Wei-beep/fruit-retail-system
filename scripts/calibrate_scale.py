"""HX711 称重传感器校准脚本（多点采集 + 线性回归）

流程：
  1. 空载去皮（tare），记录零点偏移
  2. 逐次放置砝码组合，输入总重量，脚本记录原始值
  3. 所有数据点通过线性回归计算最优 scale_factor
  4. 写入 calibration 表
  5. 空载回零验证

用法：
  python scripts/calibrate_scale.py

你手头有 100g / 50g / 20g / 20g / 10g / 1g，建议按以下顺序测量：
  第 1 组: 1g            → 输入 0.001
  第 2 组: 1g + 10g      → 输入 0.011
  第 3 组: +20g          → 输入 0.031
  第 4 组: +20g          → 输入 0.051
  第 5 组: +50g          → 输入 0.101
  第 6 组: +100g         → 输入 0.201
  输入 0 结束采集。
"""
import _bootstrap  # noqa: F401

import sys
import time

from app.core.config import load_config
from app.weighing.calibration import CalibrationService
from app.weighing.hx711_sensor import HX711Sensor


def _read_stable(sensor: HX711Sensor, samples: int = 5) -> float:
    """连续读取 3 组中位数再取平均，提高稳定性。

    gate=False：校准过程中数据库里的校准参数尚不可信，必须跳过依赖它的「越界判废」，
    否则真实承重读数可能被误判而拿不到正确数据点。
    """
    values = [sensor.read_raw_median(samples, gate=False) for _ in range(3)]
    return sum(values) / len(values)


def main() -> None:
    config = load_config()
    wc = config["weighing"]

    print("=" * 55)
    print("🍎  果蔬零售系统 — HX711 称重校准（多点采集）")
    print("=" * 55)

    # ------------------------------------------------------------------
    # 1. 初始化传感器
    # ------------------------------------------------------------------
    print(f"\n🔌 初始化 HX711（DT=GPIO{wc['dout_pin']}, SCK=GPIO{wc['sck_pin']}）...")
    try:
        sensor = HX711Sensor(
            dout_pin=wc["dout_pin"],
            sck_pin=wc["sck_pin"],
            gain=wc.get("gain", 128),
        )
    except Exception as e:
        print(f"❌ 传感器初始化失败: {e}")
        print("   请检查接线，或设置 weighing.mode: mock 使用模拟模式。")
        sys.exit(1)
    print("✅ 传感器上电成功！")

    # ------------------------------------------------------------------
    # 2. 去皮
    # ------------------------------------------------------------------
    input("\n⚖️  请确保秤盘为空，然后按 Enter 开始去皮...")
    print("   正在读取空载数据...", end=" ", flush=True)
    raw_offset = sensor.tare(samples=15)
    print(f"完成！零点偏移 = {raw_offset:.1f}")

    # ------------------------------------------------------------------
    # 3. 多点采集
    # ------------------------------------------------------------------
    print("\n📦 逐次放置砝码组合，输入总重量（单位 kg）。")
    print("   建议顺序：1g → +10g → +20g → +20g → +50g → +100g")
    print("   输入 0 结束采集，进入计算。\n")

    points: list[tuple[float, float]] = []  # [(weight_kg, raw_value), ...]
    step = 1

    while True:
        try:
            text = input(f"  第 {step} 组 — 总重量(kg, 输 0 结束): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not text:
            continue

        try:
            kg = float(text)
        except ValueError:
            print("   请输入数字。")
            continue

        if kg == 0:
            break
        if kg < 0:
            print("   重量不能为负。")
            continue

        print("   读取中...", end=" ", flush=True)
        time.sleep(0.5)
        raw = _read_stable(sensor, samples=5)
        points.append((kg, raw))
        print(f"原始值 = {raw:.1f}  ✅ 已记录")
        step += 1

    if len(points) < 1:
        print("❌ 至少需要 1 个数据点才能校准。")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 4. 线性回归计算 scale_factor
    # ------------------------------------------------------------------
    print(f"\n📊 共采集 {len(points)} 个数据点，正在计算...")

    # y = raw - offset, x = kg → scale_factor = Δraw / Δkg
    # 过原点线性回归：scale_factor = Σ(x*y) / Σ(x²)
    sum_xy = sum((w - 0) * (r - raw_offset) for w, r in points)
    sum_x2 = sum((w - 0) ** 2 for w, _ in points)

    if sum_x2 == 0:
        print("❌ 数据点不足，无法计算。")
        sys.exit(1)

    scale_factor = sum_xy / sum_x2

    print(f"\n📐 回归结果：")
    print(f"   偏移 (offset)       = {raw_offset:.1f}")
    print(f"   系数 (scale_factor)  = {scale_factor:.1f}")
    print(f"   公式: 重量(kg) = (原始值 - {raw_offset:.0f}) / {scale_factor:.0f}")

    # 打印每个点的拟合误差
    print(f"\n   {'重量(kg)':>10} | {'原始值':>10} | {'拟合值':>10} | {'误差(g)':>10}")
    print("-" * 50)
    for w, r in points:
        predicted = (r - raw_offset) / scale_factor  # 与 read_weight 一致：先减零点偏移再换算
        err_g = (w - predicted) * 1000
        print(f"   {w:>10.3f} | {r:>10.1f} | {predicted:>10.4f} | {err_g:>+9.1f}")

    # ------------------------------------------------------------------
    # 5. 写入数据库
    # ------------------------------------------------------------------
    CalibrationService().save_calibration(scale_factor, raw_offset)
    sensor.scale_factor = scale_factor
    sensor.offset = raw_offset
    print("\n✅ 校准参数已写入 calibration 表。")

    # ------------------------------------------------------------------
    # 6. 验证
    # ------------------------------------------------------------------
    input("\n🔍 移除所有砝码，保持空载，然后按 Enter 验证...")
    weight = sensor.read_weight()
    print(f"   当前显示重量: {weight:.4f} kg")
    if abs(weight) < 0.005:
        print("✅ 回零良好，校准成功！")
    elif abs(weight) < 0.02:
        print(f"⚠️  回零偏差 {weight:.4f} kg，可接受（< 20g）。")
    else:
        print(f"⚠️  回零偏差 {weight:.4f} kg，建议重复校准。")

    print("\n🎉 校准完成！将 config.yaml 中 weighing.mode 改为 real 即可启用。")


if __name__ == "__main__":
    main()
