import { Card, Row, Col, Tag, Button, Switch, Divider } from 'antd'
import { MessageOutlined, CustomerServiceOutlined, QqOutlined } from '@ant-design/icons'

export function ControlPage() {
  const channels = [
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

  return (
    <div className="space-y-4">
      <Row gutter={16}>
        <Col xs={24} md={16}>
          <Card title="控制中心" className="!bg-[#1E293B] !border-[#334155]">
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
                      <Switch checked={channel.enabled} />
                    </div>
                  </div>
                  <div className="text-xs text-[#94A3B8]">{channel.description}</div>
                </div>
              ))}
            </div>

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
            <div className="space-y-3">
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">API 端点</span>
                <Tag>https://api.tradeagent.com</Tag>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">WebSocket</span>
                <Tag>wss://ws.tradeagent.com</Tag>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">API Key</span>
                <Tag>****</Tag>
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0F172A] rounded">
                <span className="text-sm">刷新率</span>
                <Tag>1s</Tag>
              </div>
            </div>

            <Button block className="mt-4">
              配置文档
            </Button>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
