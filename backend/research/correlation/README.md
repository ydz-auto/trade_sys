# 多数据源正负相关性评估模块

## 概述

本模块实现了一套完整的多数据源正负相关性评估方案，结合统计方法、机器学习和 LLM 分析，自动识别各数据源与价格收益的正负相关性。

## 功能特性

### 1. 数据准备
- **结构化信号**: 价格、成交量、技术指标等
- **非结构化信号**: 新闻、社交媒体情感
- **滞后特征**: 自动创建多期滞后变量

### 2. 单变量分析
- **相关性分析**: Pearson、Spearman、Kendall
- **互信息**: 捕捉非线性依赖
- **Granger 因果检验**: 判断预测能力
- **滞后相关性**: 发现领先-滞后关系

### 3. 多变量分析
- **LASSO 回归**: 自动特征选择
- **XGBoost + SHAP**: 非线性建模 + 可解释性
- **随机森林**: 特征重要性

### 4. LLM 增强
- **情感趋势分析**: 时间序列聚合
- **因果推断**: 事件影响分析
- **预测评分**: 方向性预测

### 5. 综合评分
- 加权整合统计、ML、LLM 结果
- 输出信号方向 (+/-/0)
- 置信度和强度评估

### 6. 可视化
- 滞后相关性热力图
- 信号贡献柱状图
- SHAP 重要性图
- 综合评分雷达图

## 快速开始

### 基础使用

```python
import asyncio
from research.correlation import analyze_correlation

async def main():
    # 最简单的方式 - 一行代码完成分析
    result = await analyze_correlation(
        symbol="BTC",
        timeframe="1h",
        output_dir="./correlation_output"
    )
    
    print(f"正相关: {len(result.positive_signals)}")
    print(f"负相关: {len(result.negative_signals)}")
    
    # 保存结果
    result.save()

asyncio.run(main())
```

### 使用真实数据

```python
from research.correlation import analyze_correlation

# 从现有系统获取数据
news_data = await news_collector.collect()
feature_df = await get_feature_data()

result = await analyze_correlation(
    feature_df=feature_df,
    news_data=news_data,
    symbol="BTC",
    timeframe="1h"
)
```

### 高级配置

```python
from research.correlation import CorrelationAnalyzer, CorrelationConfig

config = CorrelationConfig(
    symbol="ETH",
    timeframe="15m",
    lag_windows=[1, 3, 5, 10, 20],
    significance_level=0.01,
    min_correlation=0.15,
    output_dir="./eth_analysis"
)

analyzer = CorrelationAnalyzer(config)
result = await analyzer.analyze()
```

## 模块结构

```
research/correlation/
├── __init__.py              # 模块入口
├── analyzer.py              # 主分析器
├── data_preparation.py      # 数据准备
├── univariate_analysis.py   # 单变量分析
├── multivariate_analysis.py # 多变量分析
├── llm_enhancement.py       # LLM 增强
├── scoring.py               # 综合评分
├── visualization.py         # 可视化
└── example_usage.py         # 使用示例
```

## 与现有系统集成

### 1. 对接 Feature Pipeline

```python
from research.pipeline import get_feature_pipeline
from research.correlation import analyze_correlation

pipeline = get_feature_pipeline()
# 特征数据会自动从 pipeline 获取
result = await analyze_correlation(symbol="BTC", timeframe="1h")
```

### 2. 对接 News Collector

```python
from services.data_service.collectors.news_collector import NewsCollector
from research.correlation import analyze_correlation

news_collector = NewsCollector(use_llm=True)
news_result = await news_collector.collect()
news_data = [item.to_dict() for item in news_result.data]

result = await analyze_correlation(news_data=news_data, symbol="BTC")
```

### 3. 作为定时任务运行

```python
# correlation_task.py
from research.correlation import analyze_correlation

async def run_analysis():
    result = await analyze_correlation(
        symbol="BTC",
        timeframe="1h",
        output_dir="/data/correlation"
    )
    
    # 保存到数据库
    await save_to_db(result.to_dict())
    
    # 强信号告警
    strong = [s for s in result.signal_assessments.values() if s.confidence > 0.8]
    if strong:
        await send_alert(f"发现 {len(strong)} 个强相关信号")

# 每小时运行
scheduler.add_job(run_analysis, 'cron', hour='*')
```

## 输出结果

### JSON 格式

```json
{
  "symbol": "BTC",
  "timeframe": "1h",
  "timestamp": "2024-01-15T10:30:00",
  "signal_assessments": {
    "rsi_14": {
      "feature": "rsi_14",
      "direction": "negative",
      "confidence": 0.75,
      "strength": 0.32,
      "scores": {
        "statistical": 0.68,
        "ml": 0.72,
        "llm": 0.45
      }
    }
  },
  "positive_signals": ["volume_ratio", "sentiment"],
  "negative_signals": ["rsi_14", "macd"],
  "neutral_signals": ["bb_position"],
  "summary": {
    "total_signals": 15,
    "positive_count": 2,
    "negative_count": 2,
    "neutral_count": 11
  }
}
```

### 可视化输出

- `lag_correlation_heatmap.png` - 滞后相关性热力图
- `signal_contribution.png` - 信号贡献柱状图
- `shap_importance.png` - SHAP 重要性图
- `comprehensive_radar.png` - 综合评分雷达图

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| symbol | str | "BTC" | 交易对 |
| timeframe | str | "1h" | 时间周期 |
| lag_windows | List[int] | [1,5,10,15] | 滞后窗口 |
| significance_level | float | 0.05 | 显著性水平 |
| min_correlation | float | 0.1 | 最小相关性阈值 |
| output_dir | str | "./correlation_output" | 输出目录 |
| generate_visualization | bool | True | 是否生成图表 |

## 依赖安装

```bash
# 基础依赖
pip install pandas numpy scipy

# 统计分析
pip install statsmodels

# 机器学习
pip install scikit-learn xgboost

# SHAP 可解释性 (可选)
pip install shap

# 可视化
pip install matplotlib seaborn
```

## 算法权重配置

默认权重配置：
- 统计相关性: 40%
- ML 模型: 40%
- LLM 增强: 20%

可在 `CorrelationScorer` 中自定义：

```python
from research.correlation import CorrelationScorer

scorer = CorrelationScorer(
    statistical_weight=0.5,
    ml_weight=0.3,
    llm_weight=0.2
)
```

## 注意事项

1. **数据质量**: 确保特征数据有足够的历史数据（建议 > 1000 条）
2. **计算资源**: XGBoost 和 SHAP 计算较耗时，大数据集请调整参数
3. **LLM 降级**: LLM 不可用时自动降级到关键词分析
4. **可视化**: 需要安装 matplotlib/seaborn，否则跳过图表生成

## 扩展开发

### 添加新的分析方法

```python
from research.correlation import UnivariateAnalyzer

class CustomAnalyzer(UnivariateAnalyzer):
    def custom_method(self, df, feature, target):
        # 实现自定义分析
        return result
```

### 自定义评分规则

```python
from research.correlation import CorrelationScorer, SignalAssessment

class CustomScorer(CorrelationScorer):
    def calculate_score(self, feature, univariate, multivariate, llm):
        # 自定义评分逻辑
        return SignalAssessment(...)
```

## 许可证

MIT License
