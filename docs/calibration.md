# 称重校准

HX711 称重传感器需要校准才能将原始 ADC 读数转换为 kg 重量。校准涉及两个参数：

- `offset`：空载时的原始 ADC 中位数（零点偏移）
- `scale_factor`：每 kg 对应的原始 ADC 差值（缩放系数）

## 校准流程

使用交互式脚本 `scripts/calibrate_scale.py` 完成，全程分 4 步：

### 1. 准备

```bash
source .venv/bin/activate
python scripts/calibrate_scale.py
```

### 2. 空载去皮

脚本提示后，**确保秤盘为空**，按 Enter。传感器将连续读取 15 次原始值取中位数，存入 `offset`。

### 3. 多点采集

逐次放置砝码，每次输入当前总重量（kg）。脚本会记录每个点的原始值。

建议用你手头的砝码（100g / 50g / 20g / 20g / 10g / 1g）按累积方式测量：

| 步骤 | 放置砝码       | 总重量 | 输入    |
| ---- | -------------- | ------ | ------- |
| 1    | 1g             | 1g     | `0.001` |
| 2    | +10g           | 11g    | `0.011` |
| 3    | +20g           | 31g    | `0.031` |
| 4    | +20g（第二个） | 51g    | `0.051` |
| 5    | +50g           | 101g   | `0.101` |
| 6    | +100g          | 201g   | `0.201` |

输入 `0` 结束采集。

### 4. 线性回归

脚本对所有数据点做过原点线性回归：

```
scale_factor = Σ(重量 × 原始值) / Σ(重量²)
```

相比单点测量，多点回归能有效降低随机误差，提高全量程精度。结果会同时显示每个点的拟合误差（g），方便评估线性度。

### 5. 自动写入

计算结果自动写入 `calibration` 表：

```text
scale_factor = 52341.5 (示例值，以实际为准)
offset       = 80623.1
```

## 验证

校准脚本最后会自动执行回零验证。也可以单独运行：

```bash
python scripts/weighing_test.py
```

观察空载和负载时的显示重量是否合理。

## 启用真实模式

项目默认 `weighing.mode` 已为 `real`；若开发期间切到了 `mock`，校准完成后改回 `real` 即可：

```yaml
weighing:
  mode: real
```

此时启动 GUI 或交易流程会使用真实 HX711 称重。

## 重新校准

每次更换传感器、改变机械结构或发现称重不准时，重新运行校准脚本即可。新参数会覆盖旧数据。

## 手动读写校准参数

```python
from app.weighing.calibration import CalibrationService

# 读取
cal = CalibrationService().get_calibration()
print(cal["scale_factor"], cal["offset"])

# 写入
CalibrationService().save_calibration(52341.5, 80623.1)
```

## 公式

```
重量(kg) = (原始ADC值 - offset) / scale_factor
```
