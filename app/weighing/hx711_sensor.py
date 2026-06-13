"""HX711 称重传感器驱动（树莓派 GPIO 直驱版）

接线对照（BCM 编号）：
  HX711 VCC → Pin 2  (5V)
  HX711 GND → Pin 6  (GND)
  HX711 DT  → Pin 11 (GPIO 17)
  HX711 SCK → Pin 13 (GPIO 27)

引脚编号可通过 config.yaml 的 weighing.dout_pin / weighing.sck_pin 配置。
"""
from __future__ import annotations

import time
from typing import ClassVar

from app.core.exceptions import WeightSensorError
from app.weighing.calibration import CalibrationService
from app.weighing.hx711_interface import WeightSensor


class HX711Sensor(WeightSensor):
    _gpio: ClassVar = None  # 类级缓存，避免重复 setmode

    def __init__(
        self,
        dout_pin: int = 17,
        sck_pin: int = 27,
        gain: int = 128,
    ) -> None:
        self.dout_pin = dout_pin
        self.sck_pin = sck_pin

        if gain not in (128, 64, 32):
            raise ValueError(f"不支持的增益值: {gain}，可选 128 / 64 / 32")
        self._gain_pulses = {128: 1, 64: 3, 32: 2}[gain]

        self._init_gpio()
        self._setup_pins()
        # 从数据库加载校准参数
        cal = CalibrationService().get_calibration()
        self.offset = cal["offset"]
        self.scale_factor = cal["scale_factor"]

    # ------------------------------------------------------------------
    # GPIO 初始化（RPi.GPIO 不可用时优雅降级）
    # ------------------------------------------------------------------
    @classmethod
    def _init_gpio(cls) -> None:
        if cls._gpio is not None:
            return
        try:
            import RPi.GPIO as GPIO
            cls._gpio = GPIO
            GPIO.setmode(GPIO.BCM)
        except (ImportError, RuntimeError) as exc:
            raise WeightSensorError(
                "RPi.GPIO 不可用，无法驱动 HX711。\n"
                "  请确认在树莓派上运行，或使用 weighing.mode: mock"
            ) from exc

    def _setup_pins(self) -> None:
        GPIO = self._gpio
        GPIO.setup(self.dout_pin, GPIO.IN)
        GPIO.setup(self.sck_pin, GPIO.OUT)
        GPIO.output(self.sck_pin, False)

    # ------------------------------------------------------------------
    # 底层 HX711 通信
    # ------------------------------------------------------------------
    def _read_raw(self) -> int:
        """读取一次 HX711 原始 24 位有符号值（2's complement）。"""
        GPIO = self._gpio

        # 等待 DOUT 拉低（数据就绪），超时 1 秒
        timeout = time.monotonic() + 1.0
        while GPIO.input(self.dout_pin) != 0:
            if time.monotonic() > timeout:
                raise WeightSensorError("HX711 超时：传感器未响应，请检查接线")

        # 24 个 SCK 脉冲逐位读取 (MSB first)
        value = 0
        for _ in range(24):
            GPIO.output(self.sck_pin, True)
            value = (value << 1) | GPIO.input(self.dout_pin)
            GPIO.output(self.sck_pin, False)

        # 额外脉冲设置下一轮增益
        for _ in range(self._gain_pulses):
            GPIO.output(self.sck_pin, True)
            GPIO.output(self.sck_pin, False)

        # 2's complement → int
        if value & 0x800000:
            value -= 0x1000000

        return value

    def read_raw_average(self, samples: int = 10) -> float:
        """连续读取 samples 次并返回平均值。"""
        total = 0
        for _ in range(samples):
            total += self._read_raw()
        return total / samples

    # ------------------------------------------------------------------
    # 去皮
    # ------------------------------------------------------------------
    def tare(self, samples: int = 10) -> float:
        """空载调零：读取 samples 次原始值取平均，保存为 offset。"""
        raw = self.read_raw_average(samples)
        self.offset = raw
        return raw

    # ------------------------------------------------------------------
    # 接口实现
    # ------------------------------------------------------------------
    def read_weight(self) -> float:
        """返回一次称重结果，单位 kg。"""
        raw = self._read_raw()
        return (raw - self.offset) / self.scale_factor

    # ------------------------------------------------------------------
    # 电源管理
    # ------------------------------------------------------------------
    def power_down(self) -> None:
        """将 HX711 置入掉电模式。"""
        GPIO = self._gpio
        GPIO.output(self.sck_pin, False)
        GPIO.output(self.sck_pin, True)
        time.sleep(0.0001)

    def power_up(self) -> None:
        """唤醒 HX711。"""
        GPIO = self._gpio
        GPIO.output(self.sck_pin, False)
        time.sleep(0.0001)

    # ------------------------------------------------------------------
    # 析构清理
    # ------------------------------------------------------------------
    def __del__(self) -> None:
        if self._gpio and self._gpio.getmode() is not None:
            self._gpio.cleanup([self.dout_pin, self.sck_pin])
