import subprocess
import re

with open('/tmp/sidebar_html.html', 'r', encoding='utf-8') as f:
    content = f.read()

sections = ['监控层', '策略层', '配置层', '执行层']
items = ['数据大盘', '因子面板', 'Regime状态', '风险引擎', '决策信号', '权重配置', '版本历史', '控制中心', '仓位管理', '执行追踪']

print("=== Section Titles ===")
for section in sections:
    count = content.count(section)
    status = "✓ OK" if count == 1 else f"⚠️  Found {count} times!"
    print(f"{status} '{section}': {count}")

print("\n=== Menu Items ===")
for item in items:
    count = content.count(item)
    status = "✓ OK" if count == 1 else f"⚠️  Found {count} times!"
    print(f"{status} '{item}': {count}")

print("\n=== Summary ===")
all_ok = True
for section in sections:
    if content.count(section) != 1:
        all_ok = False
        break
for item in items:
    if content.count(item) != 1:
        all_ok = False
        break

if all_ok:
    print("✅ All navigation items appear exactly once!")
else:
    print("❌ Some items are duplicated")
