import { Card, Row, Col, Tag, Button, Divider } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useTradingStore } from '../store/tradingStore'

export function DecisionPage() {
  const { signal } = useTradingStore()

  const signalTagColor = {
    BUY: 'green',
    SELL: 'red',
    HOLD: 'default',
  }[signal.action] || 'default'

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={24} md={16}>
          <Card title="决策信号" className="!bg-[#1E293B] !border-[#334155]">
            <div className="text-center py-8">
              <Tag color={signalTagColor} className="text-2xl px-6 py-2">
                {signal.action} SIGNAL
              </Tag>

              <Row gutter={24} className="mt-8">
                <Col xs={8} md={8}>
                  <div className="bg-[#0F172A] rounded-lg p-4">
                    <div className="text-[#94A3B8] text-sm mb-2">置信度</div>
                    <div className="font-mono text-2xl text-[#F59E0B]">{signal.confidence}%</div>
                  </div>
                </Col>
                <Col xs={8} md={8}>
                  <div className="bg-[#0F172A] rounded-lg p-4">
                    <div className="text-[#94A3B8] text-sm mb-2">风险等级</div>
                    <div
                      className={`font-mono text-2xl ${
                        signal.riskLevel === 'LOW'
                          ? 'text-[#10B981]'
                          : signal.riskLevel === 'MEDIUM'
                          ? 'text-[#F97316]'
                          : 'text-[#EF4444]'
                      }`}
                    >
                      {signal.riskLevel}
                    </div>
                  </div>
                </Col>
                <Col xs={8} md={8}>
                  <div className="bg-[#0F172A] rounded-lg p-4">
                    <div className="text-[#94A3B8] text-sm mb-2">市场状态</div>
                    <div className="font-mono text-2xl text-[#EF4444]">RISK_OFF</div>
                  </div>
                </Col>
              </Row>

              <Divider />

              <div className="text-left">
                <div className="text-[#94A3B8] text-sm mb-2">信号理由:</div>
                <div className="bg-[#0F172A] rounded-lg p-4 text-sm">
                  {signal.reason}
                </div>
              </div>

              <div className="flex gap-4 mt-6 justify-center">
                <Button type="primary" size="large" icon={<CheckCircleOutlined />}>
                  执行信号
                </Button>
                <Button size="large" icon={<CloseCircleOutlined />}>
                  忽略信号
                </Button>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="信号历史" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-3">
              {[
                { time: '10:30', action: 'BUY', confidence: 82, result: '已执行' },
                { time: '09:15', action: 'HOLD', confidence: 45, result: '已忽略' },
                { time: '08:00', action: 'SELL', confidence: 75, result: '已执行' },
                { time: '昨天 14:30', action: 'BUY', confidence: 68, result: '已执行' },
              ].map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#94A3B8]">{item.time}</span>
                    <Tag color={item.action === 'BUY' ? 'green' : item.action === 'SELL' ? 'red' : 'default'} className="text-xs">
                      {item.action}
                    </Tag>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#94A3B8]">{item.confidence}%</span>
                    <span className="text-xs text-[#10B981]">{item.result}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
