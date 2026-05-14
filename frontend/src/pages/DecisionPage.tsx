import { useState } from 'react'
import { Card, Row, Col, Tag, Button, Divider, Modal, message, Input, Progress, Typography } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, ThunderboltOutlined, BulbOutlined, WarningOutlined } from '@ant-design/icons'
import { useTradingStore } from '../store/tradingStore'
import { executeOrder } from '../services/api/tradingApi'

const { Title, Text, Paragraph } = Typography

export function DecisionPage() {
  const { signal, regime, factors, risk, fearGreed, prices } = useTradingStore()
  const [loading, setLoading] = useState(false)
  const [confirmModal, setConfirmModal] = useState(false)
  const [ignoreReason, setIgnoreReason] = useState('')

  const signalTagColor = {
    BUY: 'green',
    SELL: 'red',
    HOLD: 'default',
  }[signal.action] || 'default'

  // 计算因子贡献
  const calculateFactorContributions = () => {
    if (!factors || factors.length === 0) return []
    
    return factors.map(f => ({
      ...f,
      contribution: (f.value * f.weight / 100).toFixed(3)
    })).sort((a, b) => Math.abs(parseFloat(b.contribution)) - Math.abs(parseFloat(a.contribution)))
  }

  const factorContributions = calculateFactorContributions()

  // 获取持仓理由
  const getNoTradeReason = () => {
    const reasons = []
    if (risk.total > 70) {
      reasons.push("风险指数过高 (" + risk.total + ")")
    }
    if (signal.confidence < 40) {
      reasons.push("信号置信度过低 (" + signal.confidence + "%)")
    }
    const factorDisagreement = factorContributions.filter(f => 
      (signal.action === 'BUY' && parseFloat(f.contribution) < 0) || 
      (signal.action === 'SELL' && parseFloat(f.contribution) > 0)
    )
    if (factorDisagreement.length > 2) {
      reasons.push("多个因子方向冲突")
    }
    return reasons
  }

  const noTradeReasons = signal.action === 'HOLD' ? getNoTradeReason() : []

  // 获取当前BTC价格
  const btcPrice = prices.find(p => p.symbol === 'BTC')?.price || 0
  const btcChange = prices.find(p => p.symbol === 'BTC')?.change24h || 0

  const handleExecuteSignal = () => {
    setConfirmModal(true)
  }

  const confirmExecuteSignal = async () => {
    setLoading(true)
    try {
      if (signal.action === 'HOLD') {
        message.info('当前信号为HOLD，无需执行')
        return
      }

      const result = await executeOrder({
        symbol: 'BTC/USDT',
        side: signal.action,
        quantity: 0.1,
        orderType: 'MARKET',
        exchange: 'BINANCE',
        marketType: 'USDT_FUTURES',
      })

      if (result.success) {
        message.success(`信号执行成功! 订单ID: ${result.orderId}`)
      } else {
        message.error(`信号执行失败: ${result.error || '未知错误'}`)
      }
    } catch (error) {
      message.error('执行请求失败')
    } finally {
      setLoading(false)
      setConfirmModal(false)
    }
  }

  const handleIgnoreSignal = () => {
    if (!ignoreReason) {
      message.warning('请输入忽略原因')
      return
    }
    message.info(`信号已忽略: ${ignoreReason}`)
    setIgnoreReason('')
  }

  const signalHistory = [
    { time: '10:30', action: 'BUY', confidence: 82, result: '已执行' },
    { time: '09:15', action: 'HOLD', confidence: 45, result: '已忽略' },
    { time: '08:00', action: 'SELL', confidence: 75, result: '已执行' },
    { time: '昨天 14:30', action: 'BUY', confidence: 68, result: '已执行' },
  ]

  return (
    <div className="space-y-4">
      {/* AI 解释面板 - 顶部 */}
      <Card 
        title={<span className="flex items-center gap-2"><ThunderboltOutlined /> AI 信号解释</span>}
        className="!bg-[#1E293B] !border-[#334155]"
      >
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <div className="bg-[#0F172A] rounded-lg p-4 text-center">
              <div className="text-[#94A3B8] text-xs mb-2">当前信号</div>
              <Tag color={signalTagColor} className="text-xl px-4 py-1 mb-2">
                {signal.action}
              </Tag>
              <div className="text-[#94A3B8] text-sm">
                {signal.action === 'BUY' ? '建议建仓多单' : 
                 signal.action === 'SELL' ? '建议建仓空单' : '建议观望'}
              </div>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div className="bg-[#0F172A] rounded-lg p-4 text-center">
              <div className="text-[#94A3B8] text-xs mb-2">置信度来源</div>
              <Progress
                type="circle"
                percent={signal.confidence}
                width={80}
                strokeColor={
                  signal.confidence > 70 ? '#10B981' :
                  signal.confidence > 40 ? '#F59E0B' : '#EF4444'
                }
              />
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div className="bg-[#0F172A] rounded-lg p-4">
              <div className="text-[#94A3B8] text-xs mb-2">市场快照</div>
              <div className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-[#94A3B8]">BTC/USDT:</span>
                  <span className="font-mono text-[#F8FAFC]">${btcPrice.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#94A3B8]">24h变化:</span>
                  <span className={`font-mono ${btcChange >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                    {btcChange >= 0 ? '+' : ''}{btcChange.toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-[#94A3B8]">恐慌贪婪:</span>
                  <span className="font-mono text-[#F59E0B]">{fearGreed?.value || 50} ({fearGreed?.classification || 'Neutral'})</span>
                </div>
              </div>
            </div>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        <Col xs={24} md={16}>
          {/* 因子贡献分析 */}
          <Card 
            title={<span className="flex items-center gap-2"><BulbOutlined /> 因子贡献分析</span>}
            className="!bg-[#1E293B] !border-[#334155] mb-4"
          >
            <div className="space-y-3">
              {factorContributions.map((factor, idx) => (
                <div key={factor.type} className="flex items-center justify-between bg-[#0F172A] rounded p-3">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-8 h-8 rounded flex items-center justify-center text-white"
                      style={{ backgroundColor: factor.color || '#6B7280' }}
                    >
                      {factor.nameEn?.charAt(0) || factor.type.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="font-medium text-[#F8FAFC]">{factor.name}</div>
                      <div className="text-xs text-[#94A3B8]">{factor.nameEn || factor.type}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right w-32">
                      <div className={`text-lg font-mono font-bold ${parseFloat(factor.contribution) >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'}`}>
                        {parseFloat(factor.contribution) >= 0 ? '+' : ''}{factor.contribution}
                      </div>
                      <div className="text-xs text-[#94A3B8]">贡献度</div>
                    </div>
                    <div className="w-24">
                      <Progress
                        percent={Math.min(100, Math.abs(parseFloat(factor.contribution) * 200))}
                        strokeColor={parseFloat(factor.contribution) >= 0 ? '#10B981' : '#EF4444'}
                        trailColor="#334155"
                        size="small"
                        showInfo={false}
                      />
                      <div className="text-xs text-center text-[#94A3B8] mt-1">权重 {factor.weight}%</div>
                    </div>
                    <Tag color={factor.confidence > 70 ? 'green' : factor.confidence > 50 ? 'orange' : 'default'}>
                      {factor.confidence}% 可信
                    </Tag>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* 决策信号操作 */}
          <Card 
            title="信号执行"
            className="!bg-[#1E293B] !border-[#334155]"
          >
            <div className="text-center py-6">
              <Tag color={signalTagColor} className="text-2xl px-6 py-2 mb-4">
                {signal.action} SIGNAL
              </Tag>

              <Row gutter={24} className="mb-6">
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
                    <div className="font-mono text-2xl" style={{ 
                      color: regime.state === 'RISK_OFF' || regime.state === 'PANIC' ? '#EF4444' : 
                             regime.state === 'RISK_ON' || regime.state === 'EUPHORIA' ? '#10B981' : '#F59E0B'
                    }}>
                      {regime.state}
                    </div>
                  </div>
                </Col>
              </Row>

              <Divider />

              <div className="text-left mb-6">
                <div className="text-[#94A3B8] text-sm mb-2">信号理由:</div>
                <div className="bg-[#0F172A] rounded-lg p-4 text-sm">
                  {signal.reason}
                </div>
              </div>

              {signal.action === 'HOLD' && noTradeReasons.length > 0 && (
                <div className="text-left mb-6">
                  <div className="text-[#94A3B8] text-sm mb-2 flex items-center gap-2">
                    <WarningOutlined /> 不开仓原因:
                  </div>
                  <div className="space-y-1">
                    {noTradeReasons.map((reason, idx) => (
                      <div key={idx} className="bg-[#F59E0B]/10 border border-[#F59E0B]/30 rounded p-2 text-sm text-[#F59E0B]">
                        • {reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-4 mt-6 justify-center">
                <Button 
                  type="primary" 
                  size="large" 
                  icon={<CheckCircleOutlined />}
                  loading={loading}
                  onClick={handleExecuteSignal}
                  disabled={signal.action === 'HOLD'}
                >
                  执行信号
                </Button>
                <Button 
                  size="large" 
                  icon={<CloseCircleOutlined />}
                  onClick={() => {
                    Modal.confirm({
                      title: '忽略信号',
                      content: (
                        <div>
                          <p>确定要忽略当前的 {signal.action} 信号吗？</p>
                          <Input.TextArea 
                            placeholder="请输入忽略原因" 
                            onChange={(e) => setIgnoreReason(e.target.value)}
                            rows={2}
                          />
                        </div>
                      ),
                      onOk: handleIgnoreSignal,
                    });
                  }}
                >
                  忽略信号
                </Button>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="信号历史" className="!bg-[#1E293B] !border-[#334155]">
            <div className="space-y-3">
              {signalHistory.map((item, idx) => (
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

      <Modal
        title="确认执行信号"
        open={confirmModal}
        onOk={confirmExecuteSignal}
        onCancel={() => setConfirmModal(false)}
        okText="确认执行"
        cancelText="取消"
        okButtonProps={{ type: 'primary', danger: signal.action === 'SELL' }}
        confirmLoading={loading}
      >
        <div className="space-y-3">
          <p>确定要执行 <strong>{signal.action}</strong> 信号吗？</p>
          <div className="bg-[#0F172A] rounded p-3">
            <div className="text-sm text-[#94A3B8]">信号详情:</div>
            <div className="mt-2 space-y-1">
              <div>置信度: <Tag color="orange">{signal.confidence}%</Tag></div>
              <div>风险等级: <Tag color={signal.riskLevel === 'LOW' ? 'green' : signal.riskLevel === 'MEDIUM' ? 'orange' : 'red'}>{signal.riskLevel}</Tag></div>
              <div>理由: {signal.reason}</div>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
