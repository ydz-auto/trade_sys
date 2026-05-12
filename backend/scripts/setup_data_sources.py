#!/usr/bin/env python3
"""
数据源快速设置脚本

运行方式：
    python scripts/setup_data_sources.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check_env_file():
    """检查 .env 文件"""
    env_path = PROJECT_ROOT / ".env"
    env_example_path = PROJECT_ROOT / ".env.example"
    
    if not env_path.exists():
        print("\n📁 .env 文件不存在，创建中...")
        if env_example_path.exists():
            import shutil
            shutil.copy(env_example_path, env_path)
            print(f"✅ 已从 .env.example 创建 .env 文件")
        else:
            print("⚠️  .env.example 不存在，请手动创建 .env 文件")
            return False
    
    return True

def show_current_config():
    """显示当前配置"""
    print_header("当前 API Key 配置状态")
    
    env_vars = [
        ("TWITTER_API_KEY", "Twitter/X API Key"),
        ("TWITTER_API_SECRET", "Twitter/X API Secret"),
        ("TWITTER_ACCESS_TOKEN", "Twitter Access Token"),
        ("TWITTER_ACCESS_TOKEN_SECRET", "Twitter Access Token Secret"),
        ("CRYPTOPANIC_API_KEY", "CryptoPanic API Key"),
        ("WHALE_ALERT_API_KEY", "Whale Alert API Key"),
    ]
    
    config_status = []
    
    for var_name, display_name in env_vars:
        value = os.environ.get(var_name, "")
        if value:
            status = f"✅ 已配置 ({value[:4]}...{value[-4:] if len(value) > 8 else ''})"
        else:
            status = "❌ 未配置"
        config_status.append((display_name, status))
    
    # 打印状态表格
    max_name_len = max(len(name) for name, _ in config_status)
    for name, status in config_status:
        print(f"  {name.ljust(max_name_len)} : {status}")
    
    return config_status

def show_instructions():
    """显示配置说明"""
    print_header("配置说明")
    
    print("\n📖 如何配置：")
    print("\n方式 1：编辑 .env 文件（推荐）")
    print("  编辑 backend/.env 文件，填入你的 API Key")
    
    print("\n方式 2：设置环境变量")
    print("  export TWITTER_API_KEY=\"your_key\"")
    print("  export CRYPTOPANIC_API_KEY=\"your_key\"")
    print("  export WHALE_ALERT_API_KEY=\"your_key\"")
    
    print("\n📚 获取 API Key 地址：")
    print("  Twitter/X : https://developer.twitter.com/en/docs/twitter-api")
    print("  CryptoPanic : https://cryptopanic.com/developers/api/")
    print("  Whale Alert : https://docs.whale-alert.io/")
    
    print("\n📝 完整文档：")
    print("  doc/交易系统/05_Data/05.10_数据源API配置指南.md")

def run_test():
    """运行测试"""
    print_header("运行数据源测试")
    
    try:
        import asyncio
        from services.data_service.adapters import get_adapter_registry
        
        print("\n🚀 开始测试所有数据源...")
        
        # 加载 .env 文件
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path)
            print("✅ 已加载 .env 文件")
        
        registry = get_adapter_registry()
        
        print("\n⏳ 正在采集数据...")
        events = asyncio.run(registry.collect_all())
        
        print(f"\n✅ 成功获取 {len(events)} 条事件")
        
        # 按来源统计
        from collections import defaultdict
        source_count = defaultdict(int)
        for event in events:
            source_count[event.source] += 1
        
        print("\n📊 按来源统计：")
        for source, count in sorted(source_count.items(), key=lambda x: -x[1]):
            print(f"  - {source} : {count} 条")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\n" + "╔══════════════════════════════════════════════════════════════╗")
    print("║                  数据源配置助手                               ║")
    print("║              Data Source Configuration Helper                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    # 检查 .env 文件
    check_env_file()
    
    # 显示当前配置
    show_current_config()
    
    # 显示说明
    show_instructions()
    
    # 询问是否运行测试
    print("\n" + "=" * 70)
    response = input("\n要运行数据源测试吗？(y/N): ").strip().lower()
    
    if response == 'y':
        success = run_test()
        if success:
            print("\n🎉 测试完成！")
        else:
            print("\n💡 提示：即使没有 API Key，也会使用模拟数据正常运行。")
    else:
        print("\n👋 配置完成后运行测试：")
        print("  PYTHONPATH=. python3 services/data_service/test_multi_source.py")

if __name__ == "__main__":
    main()
