import { useState, useEffect } from 'react'
import { Card, Row, Col, Tag, Button, Switch, Divider, Spin, message, Empty } from 'antd'
import { MessageOutlined, CustomerServiceOutlined, QqOutlined } from '@ant-design/icons'
import api from '../services/api'
import { isMockMode } from '../config/mock'

interface ControlChannel {
  name: string
  icon: React.ReactNode
  account: string
  status: string
  enabled: boolean
  description: string
}

const mockChannels: ControlChannel[] = [
  {
    name: 'Telegram Bot',
    icon: <MessageOutlined />,
    account: '@TradeAgent_Bot',
    status: 'connected',
    enabled: true,
    description: '信号通知、状态查询、远程控制',
  },
  {
    name: '飞书 Webhook',
    icon: <CustomerServiceOutlined />,
    account: '警报通知',
    status: 'connected',
    enabled: true,
    description: '重要警报推送',
  },
  {
    name: '企业微信',
    icon: <QqOutlined />,
    account: '待集成',
    status: 'disconnected',
    enabled: false,
    description: '团队协作通知',
  },
]

const commands = [
  { cmd: '/status', desc: '查看系统状态' },
  { cmd: '/signal', desc: '查看当前信号' },
  { cmd: '/position', desc: '查看当前仓位' },
  { cmd: '/pause', desc: '暂停交易' },
  { cmd: '/resume', desc: '恢复交易' },
  { cmd: '/weight', desc: '调整权重' },
]

export function ControlPage() {
  const [channels, setChannels] = useState<ControlChannel[]>([])
  const [apiConfig, setApiConfig] = useState({
    endpoint: '',
    websocket: '',
    apiKey: '****',
    refreshRate: '1s',
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const [channelsRes, configRes] = await Promise.all([
        api.get('/control/channels'),
        api.get('/config/system'),
      ])
      
      if (isMockMode) {
        setChannels(mockChannels)
      } else if (channelsRes.data && Array.isArray(channelsRes.data)) {
        setChannels(channelsRes.data)
      }
      
      if (configRes.data) {
        setApiConfig({
          endpoint: configRes.data.endpoint || window.location.origin + '/api/v1',
          websocket: configRes.data.websocket || window.location.origin.replace('http', 'ws') + '/ws/market',
          apiKey: '****',
          refreshRate: configRes.data.refreshRate || '1s',
        })
      } else {
        setApiConfig({
          endpoint: window.location.origin + '/api/v1',
          websocket: window.location.origin.replace('http', 'ws') + '/ws/market',
          apiKey: '****',
          refreshRate: '1s',
        })
      }
    } catch (error) {
      console.error('Failed to load config:', error)
      if (isMockMode) {
        setChannels(mockChannels)
      }
      setApiConfig({
        endpoint: window.location.origin + '/api/v1',
        websocket: window.location.origin.replace('http', 'ws') + '/ws/market',
        apiKey: '****',
        refreshRate: '1s',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleToggleChannel = async (index: number, enabled: boolean) => {
    const channel = channels[index]
    try {
      await api.post(`/control/channels/${channel.name}/toggle`, { enabled })
      setChannels(prev => prev.map((ch, i) => i === index ? { ...ch, enabled } : ch))
      message.success(`${channel.name} ${enabled ? '已启用' : '已禁用'}`)
    } catch (error) {
      message.error('操作失败')
    }
  }

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={24} md={16}>
          <Card title="控制中心" className="!bg-[#1E293B] !border-[#334155]">
            {loading ? (
              <div className="flex justify-center p-8">
                <Spin />
              </div>
            ) : channels.length === 0 ? (
              <Empty description="暂无控制渠道配置" />
            ) : (
              <div className="space-y-4">
                {channels.map((channel, idx) => (
                  <div key={idx} className="bg-[#0F172A] rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-[#334155] rounded-lg flex items-center justify-center text-xl">
                          {channel.icon}
                        </div>
                        <div>
                          <div className="font-medium">{channel.name}</div>
                          <div className="text-xs text-[#94A3B8]">{channel.account}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Tag color={channel.status === 'connected' ? 'green' : 'default'}>
                          {channel.status === 'connected' ? '已连接' : '未连接'}
                        </Tag>
                        <Switch 
                          checked={channel.enabled} 
                          onChange={(checked) => handleToggleChannel(idx, checked)}
                        />
                      </div>
                    </div>
                    <div className="text-xs text-[#94A3B8]">{channel.description}</div>
                  </div>
                ))}
              </div>
            )}

            <Divider />

            <div>
              <div className="text-sm text-[#94A3B8] mb-3">支持的远程命令:</div>
              <div className="flex flex-wrap gap-2">
                {commands.map((cmd) => (
                  <Tag key={cmd.cmd} className="font-mono cursor-pointer hover:bg-[#334155]">
                    {cmd.cmd}
                    <span className="text-[#94A3B8] ml-1">- {cmd.desc}</span>
                  </Tag>
                ))}
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="API 配置" className="!bg-[#1E293B] !border-[#334155]">
            {loading ? (
              <div className="flex justify-center p-4">
                <Spin />
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                  <span className="text-sm">API 端点</span>
                  <Tag className="font-mono text-xs">{apiConfig.endpoint}</Tag>
                </div>
                <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                  <span className="text-sm">WebSocket</span>
                  <Tag className="font-mono text-xs">{apiConfig.websocket}</Tag>
                </div>
                <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                  <span className="text-sm">API Key</span>
                  <Tag>{apiConfig.apiKey}</Tag>
                </div>
                <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                  <span className="text-sm">刷新率</span>
                  <Tag>{apiConfig.refreshRate}</Tag>
                </div>
              </div>
            )}

            <Button block className="mt-4">
              配置文档
            </Button>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
