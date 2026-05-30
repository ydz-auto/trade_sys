"""
特征实现完整性检查报告

分析所有已注册特征的实现状况
"""
import sys
from pathlib import Path
import pandas as pd
from typing import Dict, List, Tuple

BACKEND_ROOT = Path(__file__).parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def check_feature_completeness():
    """检查所有特征的实现完整性"""
    print("=" * 80)
    print("特征实现完整性检查报告")
    print("=" * 80)
    
    # 获取注册表
    from engines.compute.feature import get_registry
    registry = get_registry()
    
    all_features = registry.list_all()
    categories = registry.list_categories()
    
    print(f"\n总特征数: {len(all_features)}")
    print(f"类别: {categories}")
    
    # 统计报告
    report = []
    
    # 分类检查
    for cat in categories:
        features = registry.list_by_category(cat)
        print(f"\n{'='*80}")
        print(f"{cat.upper()} 特征 ({len(features)} 个):")
        print(f"{'='*80}")
        
        for feature_name in features:
            feature = registry.get(feature_name)
            if not feature:
                continue
            
            status, notes = assess_feature_completeness(feature, feature_name)
            report.append({
                "category": cat,
                "name": feature_name,
                "status": status,
                "notes": notes
            })
            
            status_icon = "✅" if status == "complete" else "⚠️" if status == "partial" else "❌"
            print(f"{status_icon} {feature_name} - {notes}")
    
    # 生成汇总报告
    print(f"\n{'='*80}")
    print("汇总统计")
    print(f"{'='*80}")
    
    df = pd.DataFrame(report)
    summary = df.groupby(["category", "status"]).size().unstack(fill_value=0)
    print(summary)
    
    # 按状态筛选
    incomplete = df[df["status"] != "complete"]
    print(f"\n{'='*80}")
    print(f"需要完善的特征 ({len(incomplete)} 个):")
    print(f"{'='*80}")
    for _, row in incomplete.iterrows():
        print(f"  - {row['category']}/{row['name']}: {row['notes']}")
    
    return report


def assess_feature_completeness(feature, feature_name: str) -> Tuple[str, str]:
    """评估单个特征的实现完整性"""
    # 获取特征的 compute 方法源代码来分析
    import inspect
    try:
        source = inspect.getsource(feature.compute)
    except Exception:
        return "unknown", "无法获取源代码"
    
    # 特征完整性评估规则
    issues = []
    
    # 检查是否只是返回 df.get()
    if "df.get" in source and "pd.Series" in source and "np.nan" in source:
        # 检查是否是简单的 passthrough
        if "return df.get" in source and len(source.splitlines()) < 10:
            issues.append("只是简单传递原始数据，无计算")
            return "placeholder", "占位符：仅从 DataFrame 读取"
    
    # 检查是否有依赖但可能计算不完整
    if ".get" in source and "pd.Series(np.nan" in source:
        issues.append("依赖外部数据列，如果不存在则返回 NaN")
    
    # 检查是否有 TODO/注释说明未实现
    if "TODO" in source or "FIXME" in source:
        issues.append("有 TODO 标记需要完善")
    
    # 特殊特征的检查
    if feature_name in [
        "spread_estimate", "spread_pct_estimate", "microprice_estimate",
        "imbalance_1", "liquidity_shift", "spoof_probability", "wall_detection"
    ]:
        issues.append("需要逐笔订单数据，当前只是占位")
        return "placeholder", f"需要原始订单/深度数据: {','.join(issues)}"
    
    # 检查 alpha 特征
    if "distance_from_ma" in feature_name or "zscore_price" in feature_name:
        if hasattr(feature, "compute") and len(inspect.getsource(feature.compute).strip()) < 200:
            # 这些特征实现相对简单
            pass
    
    # 检查是否是市场特征依赖原始数据
    if feature_name in ["funding_rate", "oi"]:
        issues.append("需要外部数据（资金费率、持仓量）")
        return "partial", f"依赖原始市场数据: {','.join(issues)}"
    
    if issues:
        return "partial", f"部分完成: {','.join(issues)}"
    
    return "complete", "实现完整"


if __name__ == "__main__":
    report = check_feature_completeness()
