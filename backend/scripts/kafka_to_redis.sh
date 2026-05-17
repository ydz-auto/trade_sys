#!/bin/bash
# 从Kafka读取真实新闻数据并写入Redis

echo "=== 从Kafka读取真实新闻数据 ==="

# 读取Kafka消息到临时文件
echo "正在从Kafka读取消息..."
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic tradeagent.events \
  --from-beginning \
  --timeout-ms 5000 \
  > /tmp/kafka_messages.json 2>&1

# 检查是否读取到消息
if grep -q "event_type" /tmp/kafka_messages.json; then
    echo "✅ 成功读取Kafka消息"
    echo "消息内容预览:"
    head -3 /tmp/kafka_messages.json | python3 -m json.tool 2>/dev/null || head -3 /tmp/kafka_messages.json
else
    echo "❌ 没有读取到消息"
    cat /tmp/kafka_messages.json
    exit 1
fi

# 使用Python解析并写入Redis
echo ""
echo "正在解析消息并写入Redis..."

python3 << 'PYTHON_SCRIPT'
import json
import sys
import redis

# 读取Kafka消息
with open('/tmp/kafka_messages.json', 'r') as f:
    lines = f.readlines()

# 解析新闻数据
news_list = []
for line in lines:
    line = line.strip()
    if not line or 'Processed' in line:
        continue
    
    try:
        event = json.loads(line)
        if event.get('event_type') == 'news':
            news_data = event.get('data', {})
            news_list.append({
                'id': news_data.get('id', ''),
                'title': news_data.get('title', ''),
                'content': news_data.get('content', ''),
                'source': news_data.get('source', ''),
                'url': news_data.get('url', ''),
                'published': news_data.get('published', 0),
                'sentiment': news_data.get('sentiment', 'neutral'),
                'sentiment_score': news_data.get('sentiment_score', 0.5),
            })
    except:
        continue

print(f"解析到 {len(news_list)} 条新闻")

if not news_list:
    print("没有找到新闻数据")
    sys.exit(1)

# 连接Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# 构建dashboard状态
dashboard_state = {
    'prices': {},
    'factors': {},
    'regime': {},
    'signals': {},
    'news': news_list[:20],  # 只取前20条
    'compositeScore': 0.5,
    'last_update': None,
    'source': 'kafka_real_data',
}

# 写入Redis
r.set('projection:dashboard:state', json.dumps(dashboard_state))

print(f"✅ 成功写入 {len(news_list[:20])} 条真实新闻到Redis")
print("\n新闻标题预览:")
for i, news in enumerate(news_list[:5], 1):
    print(f"  {i}. [{news['source']}] {news['title']}")

PYTHON_SCRIPT

echo ""
echo "=== 完成 ==="
