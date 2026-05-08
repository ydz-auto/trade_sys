import { Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, Layout, theme, Spin } from 'antd'
import { DashboardPage } from './pages/DashboardPage'
import { WeightConfigPage } from './pages/WeightConfigPage'
import { RegimePage } from './pages/RegimePage'
import { RiskPage } from './pages/RiskPage'
import { DecisionPage } from './pages/DecisionPage'
import { ControlPage } from './pages/ControlPage'
import { PositionsPage } from './pages/PositionsPage'
import { ExecutionPage } from './pages/ExecutionPage'
import { AppSidebar } from './components/AppSidebar'
import { AppHeader } from './components/AppHeader'
import { useDataLoader } from './hooks'

const { Sider, Header, Content } = Layout

function AppContent() {
  const { loading, error } = useDataLoader()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#0F172A]">
        <Spin size="large" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#0F172A]">
        <div className="text-center">
          <div className="text-red-500 mb-2">数据加载失败</div>
          <div className="text-gray-400 text-sm">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <Layout className="min-h-screen">
      <AppSidebar />
      <Layout>
        <AppHeader />
        <Content className="p-6 overflow-auto">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/factors" element={<WeightConfigPage />} />
            <Route path="/weights" element={<WeightConfigPage />} />
            <Route path="/versions" element={<WeightConfigPage />} />
            <Route path="/regime" element={<RegimePage />} />
            <Route path="/risk" element={<RiskPage />} />
            <Route path="/decision" element={<DecisionPage />} />
            <Route path="/control" element={<ControlPage />} />
            <Route path="/positions" element={<PositionsPage />} />
            <Route path="/execution" element={<ExecutionPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
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
      <AppContent />
    </ConfigProvider>
  )
}

export default App
