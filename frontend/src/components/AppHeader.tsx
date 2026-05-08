import { Layout, Button, Tag, Space, Segmented, Popconfirm } from 'antd'
import { ReloadOutlined, SettingOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { useTradingStore } from '../store/tradingStore'
import type { SystemMode } from '../types'

const { Header } = Layout

const modeConfig: Record<SystemMode, { color: string; label: string }> = {
  BACKTEST: { color: '#3B82F6', label: '回测' },
  SIMULATION: { color: '#F97316', label: '模拟' },
  LIVE: { color: '#10B981', label: '实盘' },
}

export function AppHeader() {
  const { mode, setMode, lastUpdate } = useTradingStore()
  const [showConfirm, setShowConfirm] = useState(false)

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
    <Header className="flex items-center justify-between !px-6 !py-0 border-b border-[#334155]">
      <div className="flex items-center gap-4">
        <h1 className="text-lg m-0 font-semibold text-[#F8FAFC]">{getTitle()}</h1>
        <span className="text-xs text-[#94A3B8]">实时监控 · BTC/ETH</span>
      </div>

      <Space size={16}>
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

        <Tag
          color={modeConfig[mode].color}
          style={{ margin: 0 }}
        >
          {modeConfig[mode].label}
        </Tag>

        <div className="text-xs text-[#94A3B8]">
          最后更新: {lastUpdate.toLocaleTimeString('zh-CN', { hour12: false })}
        </div>

        <Button
          type="text"
          icon={<ReloadOutlined />}
          className="text-[#94A3B8]"
        />

        <Button
          type="text"
          icon={<SettingOutlined />}
          className="text-[#94A3B8]"
        />

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
      </Space>
    </Header>
  )
}
