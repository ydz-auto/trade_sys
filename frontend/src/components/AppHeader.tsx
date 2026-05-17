import { Layout, Button, Segmented, Popconfirm, Dropdown, App } from 'antd'
import { ReloadOutlined, MenuOutlined, SyncOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useTradingStore } from '../store/tradingStore'
import type { SystemMode } from '../types'
import type { MenuProps } from 'antd'
import api from '../services/api'

const { Header } = Layout
const { useApp } = App

interface RefreshResponse {
  success: boolean
  message: string
  data_type?: string
  timestamp?: string
  results?: RefreshResponse[]
}

interface AppHeaderProps {
  onMobileMenuToggle?: () => void
}

export function AppHeader({ onMobileMenuToggle }: AppHeaderProps) {
  const { mode, setMode } = useTradingStore()
  const { message } = useApp()
  const [showConfirm, setShowConfirm] = useState(false)
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshType, setRefreshType] = useState<string | null>(null)

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const handleRefresh = async (type: 'all' | 'prices' | 'signals' | 'factors' | 'news' = 'all') => {
    setRefreshing(true)
    setRefreshType(type)
    try {
      const response = await api.post<RefreshResponse>(`/refresh/${type}`)
      if (response.success) {
        message.success(response.message || `${type === 'all' ? '全部数据' : type}刷新成功`)
      } else {
        message.warning(response.message || '刷新完成，部分数据可能未更新')
      }
    } catch (error) {
      console.error('Refresh failed:', error)
      message.error('刷新失败，请稍后重试')
    } finally {
      setRefreshing(false)
      setRefreshType(null)
    }
  }

  const refreshMenuItems: MenuProps['items'] = [
    {
      key: 'all',
      label: '刷新全部',
      icon: <SyncOutlined spin={refreshing && refreshType === 'all'} />,
      onClick: () => handleRefresh('all'),
    },
    { type: 'divider' },
    {
      key: 'prices',
      label: '价格数据',
      onClick: () => handleRefresh('prices'),
    },
    {
      key: 'signals',
      label: '信号数据',
      onClick: () => handleRefresh('signals'),
    },
    {
      key: 'factors',
      label: '因子数据',
      onClick: () => handleRefresh('factors'),
    },
    {
      key: 'news',
      label: '新闻数据',
      onClick: () => handleRefresh('news'),
    },
  ]

  const handleModeChange = (newMode: string) => {
    if (newMode === 'LIVE' && mode !== 'LIVE') {
      setShowConfirm(true)
      return
    }
    setMode(newMode as SystemMode)
  }

  const confirmLive = () => {
    setMode('LIVE')
    setShowConfirm(false)
  }

  const getTitle = () => {
    const path = window.location.pathname
    const titles: Record<string, string> = {
      '/': '数据大盘',
      '/factors': '因子面板',
      '/weights': '权重配置',
      '/versions': '版本历史',
      '/regime': 'Regime状态',
      '/risk': '风险引擎',
      '/decision': '决策信号',
      '/control': '控制中心',
      '/positions': '仓位管理',
      '/execution': '执行追踪',
    }
    return titles[path] || 'TradeAgent'
  }

  return (
    <Header style={{ 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'space-between', 
      padding: '0 12px', 
      height: 56, 
      borderBottom: '1px solid #334155',
      backgroundColor: '#1E293B'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        {isMobile && (
          <Button
            type="text"
            icon={<MenuOutlined />}
            style={{ color: '#94A3B8', padding: '4px 8px' }}
            onClick={onMobileMenuToggle}
          />
        )}
        <h1 style={{ 
          fontSize: 14, 
          margin: 0, 
          fontWeight: 600, 
          color: '#F8FAFC', 
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis'
        }}>
          {getTitle()}
        </h1>
      </div>

      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 6,
        flexShrink: 0
      }}>
        <Segmented
          value={mode}
          onChange={handleModeChange}
          options={[
            { label: '回测', value: 'BACKTEST' },
            { label: '模拟', value: 'SIMULATION' },
            { label: '实盘', value: 'LIVE' },
          ]}
          size="small"
        />

        <Dropdown menu={{ items: refreshMenuItems }} placement="bottomRight">
          <Button
            type="text"
            icon={refreshing ? <SyncOutlined spin /> : <ReloadOutlined />}
            style={{ color: '#94A3B8', padding: '4px 8px' }}
            title="刷新数据"
          />
        </Dropdown>
      </div>

      {showConfirm && (
        <Popconfirm
          title="确认切换到实盘模式"
          description="切换到实盘模式将使用真实资金进行交易。请确保您已了解相关风险。"
          onConfirm={confirmLive}
          onCancel={() => setShowConfirm(false)}
          okText="确认实盘"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <div />
        </Popconfirm>
      )}
    </Header>
  )
}
