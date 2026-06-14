"""HX711 称重传感器驱动（树莓派 GPIO 直驱版）

接线对照（BCM 编号）：
  HX711 VCC → Pin 2  (5V)
  HX711 GND → Pin 6  (GND)
  HX711 DT  → Pin 11 (GPIO 17)
  HX711 SCK → Pin 13 (GPIO 27)

引脚编号可通过 config.yaml 的 weighing.dout_pin / weighing.sck_pin 配置。
"""
from __future__ import annotations

import mmap
import os
import statistics
import struct
import sys
import time
from typing import ClassVar

from app.core.exceptions import WeightSensorError
from app.weighing.calibration import CalibrationService
from app.weighing.hx711_interface import WeightSensor


class HX711Sensor(WeightSensor):
    _gpio: ClassVar = None  # 类级缓存，避免重复 setmode

    # 退化读数：全 0(0x000000) 或全 1(0xFFFFFF→-1)，表示 DOUT 卡死/无有效数据，
    # 按标定换算会蹦出约 ±820g 的假读数，应丢弃重读。
    _INVALID_RAW: ClassVar = (0, -1)

    # 脉冲关键段耗时上限（秒）。正常约 0.1ms；若称重线程在脉冲中途被 OS 换出致 SCK
    # 拉高超 ~60µs，芯片掉电、本次读数作废，超过此阈即判废（见 _read_raw）。
    _MAX_PULSE_SECONDS: ClassVar = 0.003

    # 掉电后芯片约数百 ms 沉降才恢复有效输出，期间每拍都是坏值。检测到打断即进入此
    # 冷却期，期间一律返回上次有效值“保持”，盖住沉降期。1.0s 覆盖 10SPS 的沉降时间。
    _SETTLE_SECONDS: ClassVar = 1.0

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

        # 最近一次脉冲关键段耗时（秒），由 _read_raw_once 写入、_read_raw 用于判废
        self._last_pulse_seconds = 0.0
        # 最近一次有效读数：沉降冷却期返回它“保持”，避免跳变
        self._last_good_raw: int | None = None
        # 沉降冷却截止时刻（monotonic 秒）；< 此刻时一律保持上次有效值
        self._settle_until = 0.0

        self._init_gpio()
        self._setup_pins()
        # 从数据库加载校准参数
        cal = CalibrationService().get_calibration()
        self.offset = cal["offset"]
        self.scale_factor = cal["scale_factor"]

        # 物理可信 raw 区间（≈[-0.5kg, 6kg]，量程上限仅 5kg 不会误杀真实商品）。
        # 落在区间外的多为位错位坏值（如 ~-0.82kg），据此判废重读。
        lo = self.offset + (-0.5) * self.scale_factor
        hi = self.offset + 6.0 * self.scale_factor
        self._raw_min = min(lo, hi)
        self._raw_max = max(lo, hi)

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
        self._init_mmap()

    # GPIO 寄存器偏移（/dev/gpiomem 起点即 GPFSEL0，各机型 BCM 偏移一致）
    _GPSET0: ClassVar = 0x1C  # 置位（拉高）pin 0-31
    _GPCLR0: ClassVar = 0x28  # 清零（拉低）pin 0-31
    _GPLEV0: ClassVar = 0x34  # 读电平 pin 0-31

    def _init_mmap(self) -> None:
        """映射 /dev/gpiomem 供位读取直接读写寄存器（纯内存操作不释放 GIL）。

        这是根治并发假读数的关键：RPi.GPIO 每次调用都释放 GIL，负载线程趁机霸占 GIL
        一个切换周期（数 ms），SCK 滞留拉高 >60µs → 掉电。映射失败或引脚 ≥32 时回退。
        """
        self._mem = None
        if self.sck_pin >= 32 or self.dout_pin >= 32:
            return  # 仅支持 GPIO 0-31（GPSET0/CLR0/LEV0），高位引脚回退
        self._sck_mask = 1 << self.sck_pin
        try:
            fd = os.open("/dev/gpiomem", os.O_RDWR | os.O_SYNC)
            try:
                self._mem = mmap.mmap(fd, 4096)
            finally:
                os.close(fd)
        except OSError:
            self._mem = None

    # ------------------------------------------------------------------
    # 底层 HX711 通信
    # ------------------------------------------------------------------
    def _read_raw(self, retries: int = 5) -> int:
        """读取一次有效原始值；检测到坏读则进入“沉降冷却·保持上次值”。

        坏读判据：脉冲段耗时超阈（被抢占致 SCK 滞留→掉电）、越界（位错位）、或全 0/全 1
        （DOUT 卡死）。打断后芯片有数百 ms 沉降期持续吐坏值且逐拍无法识别，故一旦检测到就
        进入冷却、期间返回上次有效值“保持”，盖住沉降期。无打断时即单次快读直接返回。
        """
        if time.monotonic() < self._settle_until and self._last_good_raw is not None:
            return self._last_good_raw

        last = 0
        for _ in range(retries + 1):
            value = self._read_raw_once()
            last = value
            stalled = self._last_pulse_seconds > self._MAX_PULSE_SECONDS
            out_of_range = not (self._raw_min <= value <= self._raw_max)
            if stalled or out_of_range or value in self._INVALID_RAW:
                self._settle_until = time.monotonic() + self._SETTLE_SECONDS
                if self._last_good_raw is not None:
                    return self._last_good_raw
                continue  # 启动早期尚无有效值可保持，继续尝试
            self._last_good_raw = value
            return value
        return self._last_good_raw if self._last_good_raw is not None else last

    def _read_raw_once(self) -> int:
        """读取一次 HX711 原始 24 位有符号值（2's complement）。"""
        GPIO = self._gpio

        # 等待 DOUT 拉低（数据就绪），超时 1 秒
        timeout = time.monotonic() + 1.0
        while GPIO.input(self.dout_pin) != 0:
            if time.monotonic() > timeout:
                raise WeightSensorError("HX711 超时：传感器未响应，请检查接线")

        # 时序关键段：24 个数据脉冲 + 增益脉冲。SCK 拉高须 < ~60µs，否则 HX711 掉电、
        # 本次读数作废。优先走 mmap（持 GIL、不被打断）；mmap 不可用时回退 RPi.GPIO。
        # 测量本段墙钟耗时（不含上面合法的 DOUT 就绪等待），供 _read_raw 作残余兜底判废。
        pulse_start = time.monotonic()
        if self._mem is not None:
            value = self._read_pulses_mmap()
        else:
            value = self._read_pulses_gpio()
        self._last_pulse_seconds = time.monotonic() - pulse_start

        # 2's complement → int
        if value & 0x800000:
            value -= 0x1000000

        return value

    def _read_pulses_mmap(self) -> int:
        """用 mmap 直接读写寄存器打 24+ 个 SCK 脉冲（全程持 GIL，关键段不被换出）。"""
        mem = self._mem
        set0, clr0, lev0 = self._GPSET0, self._GPCLR0, self._GPLEV0
        sck_mask = self._sck_mask
        dout_pin = self.dout_pin
        pack_into = struct.pack_into
        unpack_from = struct.unpack_from
        # 关键段内调大 GIL 切换间隔，避免解释器在迭代间隙强制本线程让出 GIL
        old_interval = sys.getswitchinterval()
        sys.setswitchinterval(1.0)
        try:
            value = 0
            for _ in range(24):
                pack_into("<I", mem, set0, sck_mask)                     # SCK 高
                bit = (unpack_from("<I", mem, lev0)[0] >> dout_pin) & 1  # 读 DOUT
                pack_into("<I", mem, clr0, sck_mask)                     # SCK 低
                value = (value << 1) | bit
            for _ in range(self._gain_pulses):                          # 增益脉冲
                pack_into("<I", mem, set0, sck_mask)
                pack_into("<I", mem, clr0, sck_mask)
        finally:
            sys.setswitchinterval(old_interval)
        return value

    def _read_pulses_gpio(self) -> int:
        """RPi.GPIO 回退位读取（每次调用释放 GIL，重负载下可能被打断，仅作兜底）。"""
        GPIO = self._gpio
        value = 0
        for _ in range(24):
            GPIO.output(self.sck_pin, True)
            value = (value << 1) | GPIO.input(self.dout_pin)
            GPIO.output(self.sck_pin, False)
        for _ in range(self._gain_pulses):
            GPIO.output(self.sck_pin, True)
            GPIO.output(self.sck_pin, False)
        return value

    def read_raw_median(self, samples: int = 10) -> float:
        """连续读取 samples 次并返回中位数。

        中位数比均值更抗离群读数：即便混入个别非哨兵的异常值（_read_raw 只剔除
        全 0 / 全 1 哨兵值），也不会把结果带偏，对去皮和校准精度更稳。
        """
        readings = [self._read_raw() for _ in range(samples)]
        return statistics.median(readings)

    # ------------------------------------------------------------------
    # 去皮
    # ------------------------------------------------------------------
    def tare(self, samples: int = 10) -> float:
        """空载调零：读取 samples 次原始值取中位数，保存为 offset。"""
        raw = self.read_raw_median(samples)
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
        mem = getattr(self, "_mem", None)
        if mem is not None:
            try:
                mem.close()
            except (BufferError, ValueError):
                pass
        if self._gpio and self._gpio.getmode() is not None:
            self._gpio.cleanup([self.dout_pin, self.sck_pin])
