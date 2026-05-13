import { useState } from 'react'
import { Card, Row, Col, Tag, Button, Divider, Modal, message, Input } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useTradingStore } from '../store/tradingStore'
import { executeOrder } from '../services/api/tradingApi'

export function DecisionPage() {
  const { signal, regime } = useTradingStore()
  const [loading, setLoading] = useState(false)
  const [confirmModal, setConfirmModal] = useState(false)
  const [ignoreReason, setIgnoreReason] = useState('')

  const signalTagColor = {
    BUY: 'green',
    SELL: 'red',
    HOLD: 'default',
  }[signal.action] || 'default'

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

              <div className="text-left">
                <div className="text-[#94A3B8] text-sm mb-2">信号理由:</div>
                <div className="bg-[#0F172A] rounded-lg p-4 text-sm">
                  {signal.reason}
                </div>
              </div>

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
