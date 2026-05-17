"""
多数据源正负相关性评估 - 使用示例

本示例展示如何：
1. 从现有系统获取数据
2. 执行完整的相关性分析
3. 获取结果并可视化
"""

import asyncio
import pandas as pd
from datetime import datetime

# 导入相关性分析模块
from research.correlation import (
    CorrelationAnalyzer,
    CorrelationConfig,
    analyze_correlation,
)


async def example_basic_usage():
    """基础使用示例 - 使用模拟数据"""
    print("=" * 60)
    print("示例 1: 基础使用 - 模拟数据")
    print("=" * 60)
    
    # 方法1: 使用便捷函数（最简单）
    result = await analyze_correlation(
        symbol="BTC",
        timeframe="1h",
        output_dir="./correlation_output",
        generate_visualization=True
    )
    
    # 查看结果
    print(f"\n分析完成!")
    print(f"正相关信号: {len(result.positive_signals)} 个")
    print(f"负相关信号: {len(result.negative_signals)} 个")
    print(f"无相关信号: {len(result.neutral_signals)} 个")
    
    # 显示前5个正相关信号
    if result.positive_signals:
        print("\n正相关信号示例:")
        for sig in result.positive_signals[:5]:
            assessment = result.signal_assessments[sig]
            print(f"  + {sig}: 置信度={assessment.confidence:.3f}, 强度={assessment.strength:.3f}")
    
    # 保存结果
    result.save()
    print(f"\n结果已保存")


async def example_with_real_data():
    """使用真实数据示例"""
    print("\n" + "=" * 60)
    print("示例 2: 使用真实数据")
    print("=" * 60)
    
    # 假设你从 data_service 获取了新闻数据
    news_data = [
        {
            "title": "Bitcoin ETF sees record inflows",
            "sentiment": "bullish",
            "sentiment_score": 0.8,
            "sentiment_confidence": 0.9,
            "published": int(datetime.now().timestamp()) - 3600,
            "is_black_swan": False,
        },
        {
            "title": "Major exchange hacked, millions stolen",
            "sentiment": "bearish",
            "sentiment_score": 0.2,
            "sentiment_confidence": 0.95,
            "published": int(datetime.now().timestamp()) - 7200,
            "is_black_swan": True,
        },
        # ... 更多新闻
    ]
    
    # 假设你从 feature_pipeline 获取了特征数据
    # 实际使用时，这里应该是真实数据
    feature_df = pd.DataFrame({
        "timestamp": pd.date_range(end=datetime.now(), periods=100, freq="1H"),
        "close": [50000 + i * 10 for i in range(100)],
        "volume": [1000 + i * 5 for i in range(100)],
        "rsi_14": [50 + (i % 20) for i in range(100)],
    })
    feature_df["returns"] = feature_df["close"].pct_change()
    feature_df.set_index("timestamp", inplace=True)
    feature_df.dropna(inplace=True)
    
    # 执行分析
    result = await analyze_correlation(
        feature_df=feature_df,
        news_data=news_data,
        symbol="BTC",
        timeframe="1h",
        lag_windows=[1, 5, 10],
        output_dir="./correlation_output"
    )
    
    print(f"\n分析完成!")
    print(f"总信号数: {len(result.signal_assessments)}")


async def example_advanced_config():
    """高级配置示例"""
    print("\n" + "=" * 60)
    print("示例 3: 高级配置")
    print("=" * 60)
    
    # 自定义配置
    config = CorrelationConfig(
        symbol="ETH",
        timeframe="15m",
        lag_windows=[1, 3, 5, 10, 20],  # 更多滞后窗口
        significance_level=0.01,  # 更严格的显著性水平
        min_correlation=0.15,  # 更高的相关性阈值
        output_dir="./eth_correlation_analysis",
        generate_visualization=True
    )
    
    # 创建分析器
    analyzer = CorrelationAnalyzer(config)
    
    # 执行分析
    result = await analyzer.analyze()
    
    # 详细分析结果
    print(f"\nETH 15分钟周期分析完成")
    print(f"分析耗时: {result.metadata.get('analysis_duration_ms', 0):.0f}ms")
    
    # 查看特定信号的详细证据
    if result.signal_assessments:
        feature = list(result.signal_assessments.keys())[0]
        assessment = result.signal_assessments[feature]
        
        print(f"\n信号 '{feature}' 详细分析:")
        print(f"  方向: {assessment.direction.value}")
        print(f"  置信度: {assessment.confidence:.3f}")
        print(f"  统计得分: {assessment.statistical_score:.3f}")
        print(f"  ML得分: {assessment.ml_score:.3f}")
        print(f"  LLM得分: {assessment.llm_score:.3f}")


async def example_integration_with_system():
    """与现有系统集成示例"""
    print("\n" + "=" * 60)
    print("示例 4: 与现有系统集成")
    print("=" * 60)
    
    # 从现有系统获取组件
    try:
        from services.data_service.collectors.news_collector import NewsCollector
        from research.pipeline import get_feature_pipeline
        
        # 获取新闻数据
        news_collector = NewsCollector(use_llm=True)
        news_result = await news_collector.collect()
        news_data = [item.to_dict() for item in news_result.data] if news_result.success else []
        
        print(f"获取到 {len(news_data)} 条新闻")
        
        # 获取特征数据
        pipeline = get_feature_pipeline()
        # 这里应该调用实际的数据获取方法
        
        # 执行相关性分析
        result = await analyze_correlation(
            news_data=news_data,
            symbol="BTC",
            timeframe="1h"
        )
        
        # 将结果发送到前端/dashboard
        dashboard_data = {
            "positive_signals": result.positive_signals,
            "negative_signals": result.negative_signals,
            "timestamp": result.timestamp.isoformat(),
            "summary": result.to_dict()["summary"]
        }
        
        print(f"\nDashboard 数据已准备: {len(dashboard_data['positive_signals'])} 正相关, "
              f"{len(dashboard_data['negative_signals'])} 负相关")
        
    except ImportError as e:
        print(f"系统集成需要实际环境: {e}")


def example_scheduled_task():
    """
    作为定时任务运行的示例
    
    可以在你的 scheduler 中添加：
    """
    code_example = '''
# correlation_task.py
import asyncio
from research.correlation import analyze_correlation

async def run_correlation_analysis():
    """定时执行相关性分析"""
    result = await analyze_correlation(
        symbol="BTC",
        timeframe="1h",
        output_dir="/data/correlation_results"
    )
    
    # 保存到数据库或发送到消息队列
    await save_to_database(result.to_dict())
    
    # 触发告警（如果发现强相关信号）
    strong_signals = [
        s for s in result.signal_assessments.values()
        if s.confidence > 0.8
    ]
    
    if strong_signals:
        await send_alert(f"发现 {len(strong_signals)} 个强相关信号")

# 在 scheduler 中注册
# 每小时执行一次
scheduler.add_job(run_correlation_analysis, 'cron', hour='*')
    '''
    print("\n" + "=" * 60)
    print("示例 5: 定时任务集成代码")
    print("=" * 60)
    print(code_example)


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("多数据源正负相关性评估 - 完整示例")
    print("=" * 60)
    
    # 运行示例
    await example_basic_usage()
    await example_with_real_data()
    await example_advanced_config()
    await example_integration_with_system()
    example_scheduled_task()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
