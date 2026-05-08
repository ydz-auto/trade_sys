import { Layout, Menu, Badge } from 'antd'
import {
  DashboardOutlined,
  AreaChartOutlined,
  SafetyCertificateOutlined,
  AlertOutlined,
  FileTextOutlined,
  SettingOutlined,
  HistoryOutlined,
  MessageOutlined,
  InboxOutlined,
  ThunderboltOutlined,
  FundProjectionScreenOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTradingStore } from '../store/tradingStore'

const { Sider } = Layout

const menuItems: MenuProps['items'] = [
  {
    key: 'monitoring',
    type: 'group',
    label: '监控层',
    children: [
      { key: '/', icon: <DashboardOutlined />, label: '数据大盘' },
      { key: '/factors', icon: <AreaChartOutlined />, label: '因子面板' },
    ],
  },
  {
    key: 'strategy',
    type: 'group',
    label: '策略层',
    children: [
      { key: '/regime', icon: <SafetyCertificateOutlined />, label: 'Regime状态' },
      { key: '/risk', icon: <AlertOutlined />, label: '风险引擎' },
      { key: '/decision', icon: <FileTextOutlined />, label: '决策信号' },
    ],
  },
  {
    key: 'config',
    type: 'group',
    label: '配置层',
    children: [
      { key: '/weights', icon: <SettingOutlined />, label: '权重配置' },
      { key: '/versions', icon: <HistoryOutlined />, label: '版本历史' },
      {
        key: '/control',
        icon: <MessageOutlined />,
        label: (
          <span className="flex items-center gap-2">
            控制中心
            <Badge count="API" size="small" style={{ backgroundColor: '#3B82F6' }} />
          </span>
        ),
      },
    ],
  },
  {
    key: 'execution',
    type: 'group',
    label: '执行层',
    children: [
      { key: '/positions', icon: <InboxOutlined />, label: '仓位管理' },
      { key: '/execution', icon: <ThunderboltOutlined />, label: '执行追踪' },
    ],
  },
]

export function AppSidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { mode, isConnected } = useTradingStore()

  const onClick: MenuProps['onClick'] = (e) => {
    navigate(e.key)
  }

  return (
    <Sider width={220} className="overflow-auto">
      <div className="h-16 flex items-center gap-3 px-4 border-b border-[#334155]">
        <div className="w-8 h-8 bg-[#F59E0B] rounded-lg flex items-center justify-center">
          <FundProjectionScreenOutlined className="text-[#0F172A] text-lg" />
        </div>
        <div>
          <div className="font-semibold text-sm text-white">TradeAgent</div>
          <div className="text-xs text-[#94A3B8]">Trading System</div>
        </div>
      </div>

      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={onClick}
        className="!border-none"
        theme="dark"
      />

      <div className="p-4 border-t border-[#334155]">
        <div className="flex items-center gap-2 mb-2">
          <Badge status={isConnected ? 'success' : 'error'} />
          <span className="text-xs text-[#94A3B8]">
            {isConnected ? '系统正常' : '系统异常'}
          </span>
        </div>
        <div
          className={`inline-block px-2 py-0.5 rounded text-xs ${
            mode === 'LIVE'
              ? 'bg-[#10B981]/20 text-[#10B981]'
              : mode === 'SIMULATION'
              ? 'bg-[#F97316]/20 text-[#F97316]'
              : 'bg-[#3B82F6]/20 text-[#3B82F6]'
          }`}
        >
          {mode === 'LIVE' ? '实盘' : mode === 'SIMULATION' ? '模拟' : '回测'}
        </div>
        <div className="text-xs text-[#94A3B8] mt-1">v2.1.0</div>
      </div>
    </Sider>
  )
}
