# engine

> 请在此描述模块的核心功能、解决的问题和主要用途。
> 例如：本模块提供 X 功能，用于解决 Y 问题。

## 概述

<!-- 描述这个模块是什么，解决什么问题 -->

## 特性

<!-- 列出模块的主要特性，每项应包含简短描述 -->

- **特性1**: 请描述第一个主要特性
- **特性2**: 请描述第二个主要特性
- **特性3**: 请描述第三个主要特性

## 使用方法

### 示例

```python
from engine import main

# 初始化
obj = main()

# 执行操作
result = obj.process()
print(result)
```

## API 概览

### 函数

| 函数 | 描述 |
|------|------|
| `normalize_condition_type()` | 请补充此函数的功能描述 |
| `normalize_severity_score()` | 请补充此函数的功能描述 |
| `evaluate_stability()` | 请补充此函数的功能描述 |
| `get_latest_hospital_snapshots()` | 请补充此函数的功能描述 |
| `calculate_distance()` | 请补充此函数的功能描述 |
| `normalize_distance()` | 请补充此函数的功能描述 |
| `log_normalize_beds()` | 请补充此函数的功能描述 |
| `normalize_icu()` | 请补充此函数的功能描述 |
| `haversine_km()` | 请补充此函数的功能描述 |
| `score_hospital()` | 请补充此函数的功能描述 |

## 目录结构

```
engine/
├── __init__.py
├── dispatch_engine.py
├── haversine.py
├── ml_scorer.py
├── stability_engine.py
```

## 相关文档

- [设计文档](DESIGN.md)

## 部署安全要求

- `MODEL_SHA256` 是强制环境变量，必须设置为 `backend/ml_training/hospital_model.pkl` 的 SHA256 值。
- 启动时会执行模型完整性校验：缺失或校验失败会直接抛错并阻止服务启动。
- 生产与 CI 必须显式注入该变量，禁止依赖默认值或省略该变量。
