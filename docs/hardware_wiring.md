# 硬件接入说明

## HX711 称重模块（已接入）

### 接线对照

| HX711 引脚 | 树莓派引脚       | BCM GPIO |
| ---------- | ---------------- | -------- |
| VCC        | Pin 2 (5V)       | —        |
| GND        | Pin 6 (GND)      | —        |
| DT         | Pin 11 (GPIO 17) | 17       |
| SCK        | Pin 13 (GPIO 27) | 27       |

引脚编号通过 `config.yaml` 中 `weighing.dout_pin` / `weighing.sck_pin` 配置，树莓派使用 **BCM 编号模式**。

### 物理接线示意（Pi 40-pin Header）

```
            ┌──────────────────────┐
            │  ○  ○  ○  ○  ○  ○  │
            │  ○  ○  ○  ○  ○  ○  │
  Pin 1 ────┤  ●  ● ←──────────● │ ←── Pin 40
  (3.3V)    │  │  │  ○  ○  ○  │  │
            │  │  │  ○  ○  ○  │  │
            │  │  │  ○  ○  ○  │  │
            │  │  │  ○  ○  ○  ├  │
            │  │  │  ○  ○  ○  │  │
            │  │  │  ○  ○  ───┤  │
            │  │  │  ○  ○  ○  │  │
            │  │  │  ○  ○  ○  │  │
            │  │  └──┤  ○  ○  │  │
            │  │     ○  ○  ○  │  │
            │  └────┤  ○  ○  │  │
            │        ○  ○  ○  │  │
            │  ● ←────────────┘  │
            └──────────────────────┘
  Pin 2 ───── 5V          HX711 VCC
  Pin 6 ───── GND         HX711 GND
  Pin 11 ──── GPIO 17     HX711 DT
  Pin 13 ──── GPIO 27     HX711 SCK
```

### 驱动代码

HX711 驱动实现在 `app/weighing/hx711_sensor.py`，通过位操作读取 24 位 ADC 值。

通信协议：
1. HX711 数据就绪后将 DOUT 拉低
2. 主控发送 25 个 SCK 脉冲（增益 128）：24 个读取数据位 + 1 个选择下一轮增益
3. 数据为 24 位 2's complement，MSB 在先
4. 返回 int 类型原始值

### 时序与并发（重要，别改回纯 RPi.GPIO）

HX711 有一条硬性时序：**SCK 拉高超过约 60µs 芯片即掉电，本次读数作废**（高位被清零 → 换算成约 +840g；位错位 → 约 -820g 假读数）。

那 25 个脉冲因此**必须用 mmap 直接读写 GPIO 寄存器**（`GPSET0/GPCLR0/GPLEV0`，纯内存操作不释放 GIL），让整段脉冲全程持有 GIL、不被线程切换打断。原因：`RPi.GPIO` 的每次 `output/input` 都会释放 GIL，在 Web 这种多线程进程里（`imencode`/uvicorn/推流等并发），`拉高SCK` 后的释放点会被其他线程抢走 GIL 跑满一个切换周期（约数 ms），SCK 滞留拉高 → 掉电 → 假读数。单线程脚本（`weighing_test.py`）无人抢 GIL 故一直正常，但 `main.py` 跑 Web 前端时就会跳变。

- 仅时序关键的 25 拍走 mmap；**DOUT 就绪等待仍用 `RPi.GPIO`**（SCK 为低、无害，且其释放 GIL 可在等待期间不阻塞其他线程）。
- 残余兜底：`_read_raw` 对极偶发的 OS 级抢占（耗时超阈 / 越界 / 全 0/全 1）判废，并在芯片掉电后的数百 ms 沉降期「保持上次有效值」，避免显示跳变。
- mmap 映射失败或引脚 ≥32 时自动回退到 `RPi.GPIO` 位读取。

### 校准

首次使用必须先运行校准脚本：

```bash
python scripts/calibrate_scale.py
```

校准流程：空载去皮 → 放砝码 → 计算 scale_factor → 写入 `calibration` 表。

快速验证：

```bash
python scripts/weighing_test.py
```

### 常见问题

- **传感器不响应**：检查 VCC（5V）/ GND 接线是否正确，DT/SCK 是否接反
- **读数跳变严重（电气）**：检查电源是否稳定，避免 USB 供电，使用外部 5V 电源
- **多线程下偶发 ~+840g / ~-820g 跳变**：并发抢占导致 SCK 滞留拉高、芯片掉电（见上「时序与并发」）。驱动已用 mmap 位读取根治，勿改回纯 `RPi.GPIO`
- **负载后数值不增加**：确认增益设置正确（默认 128），检查 DT 接线

## USB 摄像头（已接入）

USB 摄像头代码位置为 `app/camera/usb_camera.py`。使用 OpenCV 常开模式，640×480 分辨率，缓冲区设为 1 防止拍到过期帧。

## 7 寸 DSI 触摸屏

GUI 默认尺寸为 `800x480`，对应常见 7 寸触摸屏分辨率。`config.yaml` 中当前配置为：

```yaml
gui:
  width: 800
  height: 480
  fullscreen: true
  auto_set_display: true
  display: ":0"
```

`fullscreen: true` 用于让窗口铺满触摸屏。`auto_set_display: true` 用于从 SSH 会话启动 GUI 时自动尝试连接树莓派本机显示 `:0`。如果是在树莓派桌面终端中运行，也可以正常使用。

启动命令：

```bash
cd /home/pi/project/fruit_retail_system
source .venv/bin/activate
python scripts/run_gui.py
```

如果桌面会话权限阻止 SSH 进程访问显示，可以在树莓派本机桌面终端运行上述命令，或检查当前桌面环境的 `DISPLAY`、`XAUTHORITY` 和 `XDG_RUNTIME_DIR` 设置。
