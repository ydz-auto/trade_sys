import { Card, Row, Col, Tag, Progress, Steps } from 'antd'

export function RegimePage() {
  const regimeState = 'RISK_OFF'
  const confidence = 85

  const regimes = ['TRENDING', 'RANGE', 'PANIC', 'EUPHORIA', 'RISK_OFF', 'UNCERTAIN']

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="市场状态检测" className="!bg-[#1E293B] !border-[#334155]">
            <div className="flex flex-col md:flex-row items-center gap-8">
              <div className="relative w-32 h-32">
                <Progress
                  type="circle"
                  percent={confidence}
                  strokeColor="#EF4444"
                  trailColor="#334155"
                  format={() => (
                    <div className="text-center">
                      <div className="font-mono text-lg font-bold text-[#EF4444]">RISK</div>
                      <div className="font-mono text-lg font-bold text-[#EF4444]">OFF</div>
                    </div>
                  )}
                />
              </div>
              <div className="flex-1 w-full">
                <div className="text-lg font-medium mb-4">当前状态</div>
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="text-[#94A3B8]">波动率:</span>{' '}
                    <Tag color="orange">高</Tag>
                  </div>
                  <div>
                    <span className="text-[#94A3B8]">ETF流出:</span>{' '}
                    <Tag color="green">是</Tag>
                  </div>
                  <div>
                    <span className="text-[#94A3B8]">黄金上涨:</span>{' '}
                    <Tag color="orange">是</Tag>
                  </div>
                </div>
                <div className="mt-4">
                  <span className="text-[#94A3B8] text-sm">状态置信度:</span>{' '}
                  <span className="font-mono text-[#F59E0B]">{confidence}%</span>
                </div>
              </div>
            </div>

            <div className="mt-6">
              <div className="text-sm text-[#94A3B8] mb-2">状态指示:</div>
              <div className="flex flex-wrap gap-1">
                {regimes.map((r) => (
                  <div
                    key={r}
                    className={`flex-1 min-w-[80px] h-8 flex items-center justify-center text-xs rounded ${
                      r === regimeState
                        ? 'bg-[#EF4444]/30 border border-[#EF4444]/50 text-[#EF4444]'
                        : 'bg-[#334155]/50 text-[#94A3B8]'
                    }`}
                  >
                    {r}
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card title="策略生命周期" className="!bg-[#1E293B] !border-[#334155]">
            <div className="mb-4">
              <span className="font-mono text-[#F59E0B]">v2.1.0</span>{' '}
              <Tag color="green">生产</Tag>
              <span className="text-[#94A3B8] text-sm ml-4">已运行 30 天</span>
            </div>

            <Steps
              current={3}
              size="small"
              items={[
                { title: '开发' },
                { title: '影子' },
                { title: '测试' },
                { title: '生产' },
              ]}
            />

            <Row gutter={8} className="mt-6">
              <Col xs={12} md={6}>
                <div className="bg-[#0F172A] rounded p-3 text-center">
                  <div className="text-[#94A3B8] text-xs">本周PnL</div>
                  <div className="font-mono text-[#10B981]">+2.5%</div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="bg-[#0F172A] rounded p-3 text-center">
                  <div className="text-[#94A3B8] text-xs">本月PnL</div>
                  <div className="font-mono text-[#10B981]">+8.3%</div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="bg-[#0F172A] rounded p-3 text-center">
                  <div className="text-[#94A3B8] text-xs">信号一致</div>
                  <div className="font-mono text-[#F59E0B]">92%</div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="bg-[#0F172A] rounded p-3 text-center">
                  <div className="text-[#94A3B8] text-xs">资金分配</div>
                  <div className="font-mono text-[#F59E0B]">60%</div>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
