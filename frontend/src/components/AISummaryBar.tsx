import { Card, Tag, Typography, Space, Progress } from 'antd'
import { ThunderboltOutlined, AlertOutlined, RiseOutlined } from '@ant-design/icons'
import { useTradingStore } from '../store'

const { Text, Paragraph } = Typography

export function AISummaryBar() {
  const { prices, fearGreed, signal, risk, factors } = useTradingStore()

  // 计算AI Bias
  const getAIBias = () => {
    if (!signal || signal.action === 'HOLD') {
      return { label: 'Neutral', color: 'default', description: '系统正在观察市场' }
    }
    if (signal.action === 'BUY') {
      if (signal.confidence > 70) {
        return { label: 'Strongly Bullish', color: 'green', description: '多个因子显示明确多头信号' }
      }
      return { label: 'Moderately Bullish', color: 'green', description: '趋势向上，但需谨慎' }
    }
    if (signal.action === 'SELL') {
      if (signal.confidence > 70) {
        return { label: 'Strongly Bearish', color: 'red', description: '多个因子显示明确空头信号' }
      }
      return { label: 'Moderately Bearish', color: 'red', description: '趋势向下，注意风险' }
    }
    return { label: 'Neutral', color: 'default', description: '市场处于观望状态' }
  }

  const getFearGreedLabel = (value: number) => {
    if (value < 25) return { label: 'Extreme Fear', color: 'red' }
    if (value < 45) return { label: 'Fear', color: 'orange' }
    if (value < 55) return { label: 'Neutral', color: 'default' }
    if (value < 75) return { label: 'Greed', color: 'blue' }
    return { label: 'Extreme Greed', color: 'green' }
  }

  const bias = getAIBias()
  const fearGreedStatus = fearGreed ? getFearGreedLabel(fearGreed.value) : { label: 'Loading', color: 'default' }

  const aiReasons = [
    '恐慌贪婪指数: ' + (fearGreed?.value || 0) + ' (' + fearGreedStatus.label + ')',
    'BTC 24h: ' + (prices.find(p => p.symbol === 'BTC')?.change24h || 0) + '%',
    '当前信号: ' + (signal?.action || 'HOLD') + ' (置信度 ' + (signal?.confidence || 0) + '%)',
    '风险等级: ' + (risk?.level || 'medium'),
  ]

  return (
    <Card 
      size="small" 
      style={{ 
        marginBottom: 16, 
        backgroundColor: '#1E293B',
        border: '1px solid #334155',
        background: 'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)',
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'flex-start' }}>
        {/* AI Bias 主区域 */}
        <div style={{ flex: '1 1 300px', minWidth: 280 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <ThunderboltOutlined style={{ fontSize: 24, color: '#F59E0B' }} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ fontSize: 18, color: '#F8FAFC' }}>
                  AI Bias
                </Text>
                <Tag color={bias.color} style={{ fontSize: 12, fontWeight: 600 }}>
                  {bias.label}
                </Tag>
              </div>
              <Text type="secondary" style={{ fontSize: 13 }}>
                {bias.description}
              </Text>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
              综合置信度
            </Text>
            <Progress
              percent={signal?.confidence || 0}
              strokeColor={signal?.confidence > 70 ? '#10B981' : signal?.confidence > 40 ? '#F59E0B' : '#EF4444'}
              trailColor="#334155"
              size="small"
              showInfo={true}
            />
          </div>
        </div>

        {/* 原因列表 */}
        <div style={{ flex: '1 1 250px', minWidth: 220 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <RiseOutlined style={{ color: '#94A3B8' }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              关键因素
            </Text>
          </div>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {aiReasons.map((reason, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: idx === 0 ? '#10B981' : '#334155',
                }} />
                <Text style={{ fontSize: 12, color: '#94A3B8' }}>
                  {reason}
                </Text>
              </div>
            ))}
          </Space>
        </div>

        {/* 风险等级 */}
        <div style={{ flex: '0 0 180px', minWidth: 160 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <AlertOutlined style={{ color: '#94A3B8' }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              风险等级
            </Text>
          </div>
          <div style={{ 
            backgroundColor: 'rgba(0,0,0,0.2)', 
            borderRadius: 8, 
            padding: 12, 
            textAlign: 'center'
          }}>
            <Tag 
              color={
                risk?.level === 'low' ? 'green' : 
                risk?.level === 'medium' ? 'orange' : 
                risk?.level === 'high' ? 'red' : 'default'
              }
              style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}
            >
              {(risk?.level || 'medium').toUpperCase()}
            </Tag>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#F8FAFC' }}>
              {risk?.total || 0}
            </div>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {risk?.total < 40 ? '适合加仓' : risk?.total < 70 ? '谨慎操作' : '降低仓位'}
            </Text>
          </div>
        </div>
      </div>
    </Card>
  )
}
