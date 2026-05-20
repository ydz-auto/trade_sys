import { useState, useEffect } from 'react'
import { Card, Row, Col, Slider, Tabs, Tag, Button, Select, Spin, Alert, message } from 'antd'
import { SaveOutlined, ReloadOutlined, ThunderboltOutlined, RiseOutlined, LineChartOutlined, ExperimentOutlined } from '@ant-design/icons'
import {
  FeatureCategory,
  FeatureMetadata,
  FeatureValue,
  FeatureMatrixSummary,
  SymbolConfig,
  OptimizationSuggestion,
} from '../types'
import {
  getFeatureMetadata,
  getSymbolFeatures,
  getFeatureMatrixSummary,
  getAllSymbolConfigs,
  getOptimizationSuggestions,
  updateSymbolFeatures,
  triggerBacktest,
  type UpdateSymbolFeaturesRequest,
} from '../services/api/featureMatrixApi'

const { Option } = Select
const { TabPane } = Tabs

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

const CATEGORY_NAMES: Record<FeatureCategory, string> = {
  raw: '原始特征',
  derived: '衍生指标',
  microstructure: '微观结构',
  cross_market: '跨市场',
  event: '事件叙事',
}

const CATEGORY_COLORS: Record<FeatureCategory, string> = {
  raw: '#1890ff',
  derived: '#52c41a',
  microstructure: '#722ed1',
  cross_market: '#fa8c16',
  event: '#eb2f96',
}

export function FeatureConfigPage() {
  const [loading, setLoading] = useState(false)
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTCUSDT')
  
  // Feature data
  const [featureMetadata, setFeatureMetadata] = useState<FeatureMetadata[]>([])
  const [symbolFeatures, setSymbolFeatures] = useState<FeatureValue[]>([])
  const [summary, setSummary] = useState<FeatureMatrixSummary | null>(null)
  
  // Symbol config
  const [symbolConfig, setSymbolConfig] = useState<SymbolConfig | null>(null)
  const [suggestions, setSuggestions] = useState<OptimizationSuggestion[]>([])
  
  // Local weights
  const [localWeights, setLocalWeights] = useState<Record<string, number>>({})

  // Load initial data
  useEffect(() => {
    loadData()
  }, [selectedSymbol])

  const loadData = async () => {
    setLoading(true)
    try {
      const [metadata, features, summaryResp, configsResp, suggestionsResp] = await Promise.all([
        getFeatureMetadata(),
        getSymbolFeatures(selectedSymbol),
        getFeatureMatrixSummary(selectedSymbol),
        getAllSymbolConfigs(),
        getOptimizationSuggestions(selectedSymbol),
      ])

      setFeatureMetadata(metadata)
      setSymbolFeatures(features)
      setSummary(summaryResp)
      setSymbolConfig(configsResp.configs[selectedSymbol])
      setSuggestions(suggestionsResp)
      
      // Initialize local weights
      const weights: Record<string, number> = {}
      features.forEach(f => {
        weights[f.name] = f.weight
      })
      if (configsResp.configs[selectedSymbol]) {
        Object.assign(weights, configsResp.configs[selectedSymbol].weights)
      }
      setLocalWeights(weights)
    } catch (error) {
      message.error('加载数据失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleWeightChange = (featureName: string, value: number) => {
    setLocalWeights(prev => ({ ...prev, [featureName]: value }))
  }

  const handleSave = async () => {
    setLoading(true)
    try {
      const request: UpdateSymbolFeaturesRequest = {
        features: localWeights,
      }
      await updateSymbolFeatures(selectedSymbol, request)
      message.success('配置已保存')
      
      // Trigger backtest
      await triggerBacktest(selectedSymbol)
      message.info('回测已启动，建议稍后查看结果')
    } catch (error) {
      message.error('保存失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    const weights: Record<string, number> = {}
    symbolFeatures.forEach(f => {
      weights[f.name] = f.weight
    })
    setLocalWeights(weights)
  }

  const getFeaturesByCategory = (category: FeatureCategory) => {
    return symbolFeatures.filter(f => f.category === category)
  }

  const getMetadataForFeature = (name: string) => {
    return featureMetadata.find(m => m.name === name)
  }

  const renderCategoryFeatures = (category: FeatureCategory) => {
    const features = getFeaturesByCategory(category)
    if (features.length === 0) {
      return (
        <Card className="!bg-[#0F172A] !border-[#334155]">
          <div className="text-[#94A3B8] text-sm">暂无此分类特征</div>
        </Card>
      )
    }

    return (
      <div className="space-y-4">
        {features.map(feature => {
          const meta = getMetadataForFeature(feature.name)
          return (
            <Card
              key={feature.name}
              className="!bg-[#0F172A] !border-[#334155]"
              size="small"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div
                    className="w-6 h-6 rounded flex items-center justify-center"
                    style={{ backgroundColor: `${CATEGORY_COLORS[category]}20`, color: CATEGORY_COLORS[category] }}
                  >
                    {meta?.isFactor ? <RiseOutlined /> : <LineChartOutlined />}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-[#E2E8F0]">
                      {meta?.name || feature.name}
                    </div>
                    <div className="text-xs text-[#94A3B8]">
                      {meta?.nameEn || meta?.description || ''}
                    </div>
                  </div>
                  {meta?.isFactor && (
                    <Tag color="blue" className="text-xs">原因子</Tag>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-[#E2E8F0]">
                    {feature.value.toFixed(4)}
                  </div>
                  <div className="text-xs text-[#94A3B8]">
                    置信度: {feature.confidence}%
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-3">
                <Slider
                  value={localWeights[feature.name] || feature.weight}
                  onChange={(value) => handleWeightChange(feature.name, value)}
                  min={0}
                  max={100}
                  trackStyle={{ backgroundColor: CATEGORY_COLORS[category] }}
                  handleStyle={{ borderColor: CATEGORY_COLORS[category], backgroundColor: CATEGORY_COLORS[category] }}
                  className="flex-1"
                />
                <div className="w-16 text-right">
                  <span className="font-mono text-[#F59E0B]">
                    {localWeights[feature.name] || feature.weight}%
                  </span>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    )
  }

  const renderSummary = () => {
    if (!summary) return null
    
    return (
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={12} sm={6} md={4}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic title="总特征" value={summary.featuresTotal} valueStyle={{ color: '#10B981' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic title="原始特征" value={summary.featuresRaw} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic title="衍生指标" value={summary.featuresDerived} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic title="微观结构" value={summary.featuresMicrostructure} valueStyle={{ color: '#722ed1' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic title="跨市场" value={summary.featuresCrossMarket} valueStyle={{ color: '#fa8c16' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Card size="small" className="!bg-[#1E293B] !border-[#334155]">
            <Statistic title="事件叙事" value={summary.featuresEvent} valueStyle={{ color: '#eb2f96' }} />
          </Card>
        </Col>
      </Row>
    )
  }

  const renderSuggestions = () => {
    if (suggestions.length === 0) {
      return (
        <Alert
          message="暂无优化建议"
          description="当前配置表现良好，建议持续观察"
          type="info"
          showIcon
          className="!bg-[#0F172A] !border-[#334155]"
        />
      )
    }

    return (
      <div className="space-y-3">
        {suggestions.map((suggestion, index) => (
          <Card
            key={index}
            size="small"
            className="!bg-[#0F172A] !border-[#334155]"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-[#E2E8F0]">
                  {suggestion.feature}
                </div>
                <div className="text-xs text-[#94A3B8] mt-1">
                  {suggestion.reason}
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-[#94A3B8]">
                  {suggestion.currentValue.toFixed(2)} → {suggestion.suggestedValue.toFixed(2)}
                </div>
                {suggestion.expectedImprovement && (
                  <div className="text-xs text-[#10B981]">
                    +{suggestion.expectedImprovement.toFixed(2)}% 预期收益
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    )
  }

  const renderConfigSummary = () => {
    if (!symbolConfig) return null
    
    return (
      <div className="space-y-4">
        <Card size="small" className="!bg-[#0F172A] !border-[#334155]">
          <Row gutter={16}>
            <Col span={8}>
              <div className="text-xs text-[#94A3B8]">币种</div>
              <div className="text-sm font-medium text-[#E2E8F0]">{symbolConfig.symbol}</div>
            </Col>
            <Col span={8}>
              <div className="text-xs text-[#94A3B8]">启用策略数</div>
              <div className="text-sm font-medium text-[#E2E8F0]">{symbolConfig.enabledStrategies.length}</div>
            </Col>
            <Col span={8}>
              <div className="text-xs text-[#94A3B8]">最后更新</div>
              <div className="text-sm font-mono text-[#E2E8F0]">
                {new Date(symbolConfig.lastUpdated).toLocaleString()}
              </div>
            </Col>
          </Row>
        </Card>
      </div>
    )
  }

  const tabItems = [
    {
      key: 'overview',
      label: '概览',
      icon: <RiseOutlined />,
      children: (
        <div>
          {renderSummary()}
          {renderConfigSummary()}
        </div>
      ),
    },
    ...Object.entries(CATEGORY_NAMES).map(([category, name]) => ({
      key: category,
      label: name,
      children: renderCategoryFeatures(category as FeatureCategory),
    })),
    {
      key: 'suggestions',
      label: '优化建议',
      icon: <ThunderboltOutlined />,
      children: renderSuggestions(),
    },
  ]

  return (
    <Spin spinning={loading}>
      <div className="space-y-4">
        {/* Header with symbol selector */}
        <Row align="middle" gutter={16}>
          <Col xs={24} md={12}>
            <h1 className="text-xl font-bold text-[#E2E8F0] mb-0">特征矩阵配置</h1>
            <p className="text-[#94A3B8] text-sm mt-1">
              每个币种独立配置，权重调整后自动触发回测优化
            </p>
          </Col>
          <Col xs={24} md={12} className="text-right">
            <Select
              value={selectedSymbol}
              onChange={setSelectedSymbol}
              style={{ width: 180, marginRight: 16 }}
            >
              {SYMBOLS.map(symbol => (
                <Option key={symbol} value={symbol}>{symbol}</Option>
              ))}
            </Select>
            <Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} className="ml-2">
              保存并回测
            </Button>
          </Col>
        </Row>

        <Tabs items={tabItems} defaultActiveKey="overview" />
      </div>
    </Spin>
  )
}

// Re-export as default for backward compatibility
export default FeatureConfigPage
