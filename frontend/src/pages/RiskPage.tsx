import { Card, Row, Col, Progress } from 'antd'
import { useTradingStore } from '../store/tradingStore'

export function RiskPage() {
  const { risk } = useTradingStore()
  
  const riskComponents = [
    { name: '波动风险', value: risk.components.volatility, color: '#F97316' },
    { name: '资金流风险', value: risk.components.flow, color: '#10B981' },
    { name: '情绪风险', value: risk.components.sentiment, color: '#EF4444' },
    { name: '宏观风险', value: risk.components.macro, color: '#3B82F6' },
  ]

  const riskLevelColor: Record<string, string> = {
    low: '#10B981',
    medium: '#F59E0B',
    high: '#F97316',
    extreme: '#EF4444',
  }

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={24} md={16}>
          <Card title="风险引擎" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-6">
              {riskComponents.map((riskItem) => (
                <div key={riskItem.name}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-[#94A3B8]">{riskItem.name}</span>
                    <span className="font-mono" style={{ color: riskItem.color }}>
                      {(riskItem.value * 100).toFixed(0)}
                    </span>
                  </div>
                  <Progress
                    percent={riskItem.value * 100}
                    showInfo={false}
                    strokeColor={riskItem.color}
                    trailColor="#334155"
                  />
                </div>
              ))}
            </div>

            <div className="mt-8 pt-6 border-t border-[#334155]">
              <div className="flex items-center justify-between">
                <span className="text-lg font-medium">总风险指数</span>
                <span className="font-mono text-3xl font-bold" style={{ color: riskLevelColor[risk.level] || '#F97316' }}>
                  {risk.total}
                </span>
              </div>
              <div className="flex gap-6 mt-4 text-sm">
                <div>
                  <span className="text-[#94A3B8]">风险等级:</span>{' '}
                  <span style={{ color: riskLevelColor[risk.level] || '#F97316' }}>{risk.level.toUpperCase()}</span>
                </div>
                <div>
                  <span className="text-[#94A3B8]">允许交易:</span>{' '}
                  <span className="text-[#10B981]">{risk.total < 80 ? '是' : '否'}</span>
                </div>
                <div>
                  <span className="text-[#94A3B8]">最大仓位:</span>{' '}
                  <span className="text-[#F59E0B]">30%</span>
                </div>
                <div>
                  <span className="text-[#94A3B8]">最大杠杆:</span>{' '}
                  <span className="text-[#F59E0B]">2x</span>
                </div>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="风控规则" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">单日亏损止损</span>
                <span className="font-mono text-[#EF4444]">5%</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">最大回撤</span>
                <span className="font-mono text-[#F97316]">10%</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">风险指数阈值</span>
                <span className="font-mono text-[#F97316]">80</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">连续亏损限制</span>
                <span className="font-mono text-[#F59E0B]">3次</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
