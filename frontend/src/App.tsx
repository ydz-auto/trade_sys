import { Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, Layout, App as AntApp } from 'antd'
import { useState, useEffect } from 'react'
import { DashboardPage } from './pages/DashboardPage'
import { WeightConfigPage } from './pages/WeightConfigPage'
import { FeatureConfigPage } from './pages/FeatureConfigPage'
import { StrategyManagementPage } from './pages/StrategyManagementPage'
import { RegimePage } from './pages/RegimePage'
import { RiskPage } from './pages/RiskPage'
import { DecisionPage } from './pages/DecisionPage'
import { ControlPage } from './pages/ControlPage'
import { PositionsPage } from './pages/PositionsPage'
import { ExecutionPage } from './pages/ExecutionPage'
import { SystemMonitorPage } from './pages/SystemMonitorPage'
import { AlphaLifecyclePage } from './pages/AlphaLifecyclePage'
import { ReplayPage } from './pages/ReplayPage'
import { FactorAnalyticsPage } from './pages/FactorAnalyticsPage'
import { RiskPropagationPage } from './pages/RiskPropagationPage'
import { SettingsPage } from './pages/SettingsPage'
import { DataConfigPage } from './pages/DataConfigPage'
import { TradingPage } from './pages/TradingPage'
import { AppSidebar } from './components/AppSidebar'
import { AppHeader } from './components/AppHeader'
import { EventTimeline } from './components/EventTimeline'
import { useDataLoader } from './hooks'
import { RuntimeProvider } from './services/runtime'

const { Content, Footer } = Layout

const isMobile = () => window.innerWidth < 768

function AppContent() {
  const { error } = useDataLoader()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [isMobileDevice, setIsMobileDevice] = useState(false)

  useEffect(() => {
    const checkMobile = () => setIsMobileDevice(isMobile())
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  const handleCollapse = (newCollapsed: boolean) => {
    setCollapsed(newCollapsed)
  }

  // 不阻塞页面，立即显示布局
  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: '#0F172A' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: '#EF4444', marginBottom: 8 }}>数据加载失败</div>
          <div style={{ color: '#94A3B8', fontSize: 14 }}>{error}</div>
        </div>
      </div>
    )
  }

  const marginLeft = isMobileDevice ? 0 : (collapsed ? 0 : 220)

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <AppSidebar
        collapsed={collapsed}
        onCollapse={handleCollapse}
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />
      <Layout style={{ marginLeft, transition: 'margin-left 0.2s' }}>
        <AppHeader onMobileMenuToggle={() => setMobileMenuOpen(!mobileMenuOpen)} />
        <Content style={{ padding: 24, overflow: 'auto', minHeight: 'calc(100vh - 64px - 180px)' }}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/factors" element={<WeightConfigPage />} />
            <Route path="/weights" element={<WeightConfigPage />} />
            <Route path="/versions" element={<WeightConfigPage />} />
            <Route path="/features" element={<FeatureConfigPage />} />
            <Route path="/strategy" element={<StrategyManagementPage />} />
            <Route path="/factor-analytics" element={<FactorAnalyticsPage />} />
            <Route path="/regime" element={<RegimePage />} />
            <Route path="/risk" element={<RiskPage />} />
            <Route path="/risk-propagation" element={<RiskPropagationPage />} />
            <Route path="/decision" element={<DecisionPage />} />
            <Route path="/control" element={<ControlPage />} />
            <Route path="/positions" element={<PositionsPage />} />
            <Route path="/execution" element={<ExecutionPage />} />
            <Route path="/monitor" element={<SystemMonitorPage />} />
            <Route path="/alpha" element={<AlphaLifecyclePage />} />
            <Route path="/replay" element={<ReplayPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/data-config" element={<DataConfigPage />} />
            <Route path="/trading" element={<TradingPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
        <Footer style={{ padding: 0, position: 'fixed', bottom: 0, left: marginLeft, right: 0, zIndex: 999 }}>
          <EventTimeline />
        </Footer>
      </Layout>
    </Layout>
  )
}

function App() {
  return (
    <RuntimeProvider>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#F59E0B',
            colorSuccess: '#10B981',
            colorWarning: '#F97316',
            colorError: '#EF4444',
            colorInfo: '#3B82F6',
            colorBgBase: '#0F172A',
            colorBgContainer: '#1E293B',
            colorBgElevated: '#334155',
            colorBorder: '#334155',
            colorText: '#F8FAFC',
            colorTextSecondary: '#94A3B8',
            fontFamily: "'Fira Sans', -apple-system, BlinkMacSystemFont, sans-serif",
            fontFamilyCode: "'Fira Code', monospace",
            borderRadius: 8,
          },
          components: {
            Layout: {
              siderBg: '#1E293B',
              headerBg: '#1E293B',
              bodyBg: '#0F172A',
            },
            Menu: {
              darkItemBg: '#1E293B',
              darkSubMenuItemBg: '#0F172A',
            },
            Card: {
              paddingLG: 16,
            },
            Table: {
              headerBg: '#334155',
            },
          },
        }}
      >
        <AntApp>
          <AppContent />
        </AntApp>
      </ConfigProvider>
    </RuntimeProvider>
  )
}

export default App
