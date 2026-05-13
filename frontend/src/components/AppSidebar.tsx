import { Layout, Menu, Badge, Drawer, Button } from 'antd'
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
  CloseOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTradingStore } from '../store/tradingStore'
import { useState, useEffect } from 'react'

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
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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

interface AppSidebarProps {
  collapsed?: boolean
  onCollapse?: (collapsed: boolean) => void
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export function AppSidebar({ collapsed, onCollapse, mobileOpen, onMobileClose }: AppSidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { mode, isConnected } = useTradingStore()
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768)

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const onClick: MenuProps['onClick'] = (e) => {
    navigate(e.key)
    if (onMobileClose) {
      onMobileClose()
    }
  }

  const sidebarContent = () => (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#1E293B' }}>
      <div style={{ 
        height: 64, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        paddingLeft: 16, 
        paddingRight: 16, 
        borderBottom: '1px solid #334155',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ 
            width: 32, 
            height: 32, 
            backgroundColor: '#F59E0B', 
            borderRadius: 8, 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center' 
          }}>
            <FundProjectionScreenOutlined style={{ color: '#0F172A', fontSize: 18 }} />
          </div>
          {!collapsed && (
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, color: 'white' }}>TradeAgent</div>
              <div style={{ fontSize: 12, color: '#94A3B8' }}>Trading System</div>
            </div>
          )}
        </div>
        {isMobile && onMobileClose && (
          <Button
            type="text"
            icon={<CloseOutlined />}
            onClick={onMobileClose}
            style={{ color: '#94A3B8' }}
          />
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={onClick}
          style={{ borderRight: 'none', backgroundColor: 'transparent' }}
          theme="dark"
          inlineCollapsed={collapsed}
        />
      </div>

      {!collapsed && (
        <div style={{ padding: 16, borderTop: '1px solid #334155', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Badge status={isConnected ? 'success' : 'error' } />
            <span style={{ fontSize: 12, color: '#94A3B8' }}>
              {isConnected ? '系统正常' : '系统异常'}
            </span>
          </div>
          <div
            style={{
              display: 'inline-block',
              padding: '4px 8px',
              borderRadius: 4,
              fontSize: 12,
              ...(mode === 'LIVE'
                ? { backgroundColor: '#10B98120', color: '#10B981' }
                : mode === 'SIMULATION'
                ? { backgroundColor: '#F9731620', color: '#F97316' }
                : { backgroundColor: '#3B82F620', color: '#3B82F6' }),
            }}
          >
            {mode === 'LIVE' ? '实盘' : mode === 'SIMULATION' ? '模拟' : '回测'}
          </div>
          <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 4 }}>v2.1.0</div>
        </div>
      )}
    </div>
  )

  return (
    <>
      <Sider
        width={220}
        style={{ overflow: 'auto', height: '100vh', position: 'fixed', left: 0, top: 0 }}
        collapsible
        collapsed={collapsed}
        onCollapse={onCollapse}
        theme="dark"
        breakpoint="md"
        collapsedWidth="0"
      >
        {sidebarContent()}
      </Sider>

      <Drawer
        placement="left"
        onClose={onMobileClose}
        open={mobileOpen}
        width={250}
        bodyStyle={{ padding: 0, backgroundColor: '#1E293B' }}
        headerStyle={{ display: 'none' }}
        maskStyle={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
        styles={{ body: { padding: 0 } }}
      >
        {sidebarContent()}
      </Drawer>
    </>
  )
}
