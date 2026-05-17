import { useState, useEffect } from 'react'
import { Card, Form, Input, InputNumber, Switch, Button, Tabs, Space, Tag, message, Divider, List, Typography, Row, Col, Statistic } from 'antd'
import { SaveOutlined, ReloadOutlined, SettingOutlined, SafetyOutlined, ThunderboltOutlined, StockOutlined } from '@ant-design/icons'
import api from '../services/api'
import type { RiskConfig, StrategyConfig, SystemConfig, ExchangeConfig, ConfigResponse, ExchangeListResponse } from '../services/api'

const { Text, Title } = Typography

export function SettingsPage() {
  const [riskForm] = Form.useForm<RiskConfig>()
  const [strategyForm] = Form.useForm<StrategyConfig>()
  const [systemForm] = Form.useForm<SystemConfig>()
  const [exchangeConfigs, setExchangeConfigs] = useState<Record<string, ExchangeConfig>>({})
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('risk')

  useEffect(() => {
    loadAllConfigs()
  }, [])

  const loadAllConfigs = async () => {
    try {
      const [risk, strategy, system, exchanges]: [
        ConfigResponse<RiskConfig>,
        ConfigResponse<StrategyConfig>,
        ConfigResponse<SystemConfig>,
        ExchangeListResponse
      ] = await Promise.all([
        api.get('/config/risk'),
        api.get('/config/strategy'),
        api.get('/config/system'),
        api.get('/config/exchange'),
      ])
      
      riskForm.setFieldsValue(risk.config)
      strategyForm.setFieldsValue(strategy.config)
      systemForm.setFieldsValue(system.config)
      setExchangeConfigs(exchanges.exchanges || {})
    } catch (error) {
      message.error('加载配置失败')
    }
  }

  const saveRiskConfig = async () => {
    try {
      setLoading(true)
      const values = riskForm.getFieldsValue()
      await api.put('/config/risk', values)
      message.success('风控配置已保存')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setLoading(false)
    }
  }

  const saveStrategyConfig = async () => {
    try {
      setLoading(true)
      const values = strategyForm.getFieldsValue()
      await api.put('/config/strategy', values)
      message.success('策略配置已保存')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setLoading(false)
    }
  }

  const saveSystemConfig = async () => {
    try {
      setLoading(true)
      const values = systemForm.getFieldsValue()
      await api.put('/config/system', values)
      message.success('系统配置已保存')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setLoading(false)
    }
  }

  const toggleExchange = async (exchange: string, enabled: boolean) => {
    try {
      const config = exchangeConfigs[exchange]
      if (config) {
        await api.put(`/config/exchange/${exchange}`, { ...config, enabled })
        setExchangeConfigs(prev => ({
          ...prev,
          [exchange]: { ...config, enabled }
        }))
        message.success(`${exchange} ${enabled ? '已启用' : '已禁用'}`)
      }
    } catch (error) {
      message.error('更新失败')
    }
  }

  const tabs = [
    {
      key: 'risk',
      label: (
        <Space>
          <SafetyOutlined />
          风控参数
        </Space>
      ),
      children: (
        <div style={{ marginTop: 16 }}>
          <Card.Meta
            title={<span style={{ fontSize: 16, fontWeight: 600 }}>🛡️ 风控参数配置</span>}
            description={
              <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
                <p style={{ marginBottom: 4 }}>• 设置仓位限制、亏损限制、订单限制</p>
                <p style={{ marginBottom: 4 }}>• 配置默认止损止盈比例</p>
                <p style={{ marginBottom: 0 }}>• 管理交易对黑名单</p>
              </div>
            }
            style={{ marginBottom: 24 }}
          />
          <Card>
            <Form form={riskForm} layout="vertical">
              <Title level={5}><SafetyOutlined /> 仓位限制</Title>
              <Row gutter={24}>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="最大持仓价值 (USDT)" name="max_position_value">
                    <InputNumber min={0} step={1000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="最大持仓数量" name="max_position_count">
                    <InputNumber min={1} max={50} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="最大杠杆" name="max_leverage">
                    <InputNumber min={1} max={125} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Divider />
              <Title level={5}>📉 亏损限制</Title>
              <Row gutter={24}>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="日亏损限制 (%)" name="daily_loss_limit_pct">
                    <InputNumber min={0} max={50} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="回撤限制 (%)" name="drawdown_limit_pct">
                    <InputNumber min={0} max={100} step={1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Divider />
              <Title level={5}>📋 订单限制</Title>
              <Row gutter={24}>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="单笔订单限额 (USDT)" name="order_size_limit">
                    <InputNumber min={0} step={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="交易冷却期 (秒)" name="cooldown_seconds">
                    <InputNumber min={0} max={3600} step={10} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Divider />
              <Title level={5}>🎯 止损止盈</Title>
              <Row gutter={24}>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="默认止损 (%)" name="stop_loss_default_pct">
                    <InputNumber min={0} max={50} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8}>
                  <Form.Item label="默认止盈 (%)" name="take_profit_default_pct">
                    <InputNumber min={0} max={100} step={0.5} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Divider />
              <Title level={5}>🚫 黑名单</Title>
              <Form.Item label="禁止交易的交易对" name="symbol_blacklist">
                <Input.TextArea rows={2} placeholder="用逗号分隔，如: DOGE/USDT,SHIB/USDT" />
              </Form.Item>
              
              <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={saveRiskConfig}>
                保存风控配置
              </Button>
            </Form>
          </Card>
        </div>
      )
    },
    {
      key: 'strategy',
      label: (
        <Space>
          <StockOutlined />
          策略参数
        </Space>
      ),
      children: (
        <div style={{ marginTop: 16 }}>
          <Card.Meta
            title={<span style={{ fontSize: 16, fontWeight: 600 }}>⚙️ 策略因子权重配置</span>}
            description={
              <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
                <p style={{ marginBottom: 4 }}>• 配置因子权重（所有权重之和应等于 1.0）</p>
                <p style={{ marginBottom: 4 }}>• 设置信号触发阈值和最低置信度</p>
                <p style={{ marginBottom: 0 }}>• 调整策略敏感度参数</p>
              </div>
            }
            style={{ marginBottom: 24 }}
          />
          <Card>
            <Form form={strategyForm} layout="vertical">
              <Title level={5}>📊 因子权重</Title>
              <Text type="secondary">所有权重之和应该等于 1.0</Text>
              <Row gutter={24} style={{ marginTop: 16 }}>
                <Col xs={12} sm={6}>
                  <Form.Item label="趋势权重" name="trend_weight">
                    <InputNumber min={0} max={1} step={0.05} precision={2} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={12} sm={6}>
                  <Form.Item label="资金流权重" name="flow_weight">
                    <InputNumber min={0} max={1} step={0.05} precision={2} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={12} sm={6}>
                  <Form.Item label="情绪权重" name="sentiment_weight">
                    <InputNumber min={0} max={1} step={0.05} precision={2} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={12} sm={6}>
                  <Form.Item label="宏观权重" name="macro_weight">
                    <InputNumber min={0} max={1} step={0.05} precision={2} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Divider />
              <Title level={5}>🎯 信号阈值</Title>
              <Row gutter={24}>
                <Col xs={24} sm={12}>
                  <Form.Item label="信号触发阈值" name="signal_threshold">
                    <InputNumber min={0} max={1} step={0.05} precision={2} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item label="最低置信度" name="min_confidence">
                    <InputNumber min={0} max={1} step={0.05} precision={2} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={saveStrategyConfig}>
                保存策略配置
              </Button>
            </Form>
          </Card>
        </div>
      )
    },
    {
      key: 'exchange',
      label: (
        <Space>
          <StockOutlined />
          交易所
        </Space>
      ),
      children: (
        <div style={{ marginTop: 16 }}>
          <Card.Meta
            title={<span style={{ fontSize: 16, fontWeight: 600 }}>💹 交易所配置</span>}
            description={
              <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
                <p style={{ marginBottom: 4 }}>• 管理交易所连接状态</p>
                <p style={{ marginBottom: 4 }}>• 配置交易对和优先级</p>
                <p style={{ marginBottom: 0 }}>• 设置超时和重试参数</p>
              </div>
            }
            style={{ marginBottom: 24 }}
          />
          <Card>
            <List
              dataSource={Object.entries(exchangeConfigs)}
              renderItem={([name, config]) => (
                <List.Item
                  actions={[
                    <Switch
                      key="toggle"
                      checked={config.enabled}
                      onChange={(checked) => toggleExchange(name, checked)}
                    />
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <span style={{ fontSize: 16, fontWeight: 600 }}>{name.toUpperCase()}</span>
                        <Tag color={config.enabled ? 'green' : 'default'}>
                          {config.enabled ? '已启用' : '已禁用'}
                        </Tag>
                      </Space>
                    }
                    description={
                      <Row gutter={16} style={{ marginTop: 8 }}>
                        <Col><Text type="secondary">优先级: {config.priority}</Text></Col>
                        <Col><Text type="secondary">超时: {config.timeout}s</Text></Col>
                        <Col><Text type="secondary">交易对: {config.symbols.slice(0, 3).join(', ')}{config.symbols.length > 3 ? '...' : ''}</Text></Col>
                      </Row>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </div>
      )
    },
    {
      key: 'system',
      label: (
        <Space>
          <ThunderboltOutlined />
          系统
        </Space>
      ),
      children: (
        <div style={{ marginTop: 16 }}>
          <Card.Meta
            title={<span style={{ fontSize: 16, fontWeight: 600 }}>⚡ 系统配置</span>}
            description={
              <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
                <p style={{ marginBottom: 4 }}>• 配置日志级别和监控参数</p>
                <p style={{ marginBottom: 4 }}>• 设置健康检查间隔</p>
                <p style={{ marginBottom: 0 }}>• 调整回放速度</p>
              </div>
            }
            style={{ marginBottom: 24 }}
          />
          <Card>
            <Form form={systemForm} layout="vertical">
              <Title level={5}>📝 日志与监控</Title>
              <Row gutter={24}>
                <Col xs={24} sm={8}>
                  <Form.Item label="日志级别" name="log_level">
                    <Input placeholder="INFO, DEBUG, WARNING" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item label="启用指标采集" name="metrics_enabled" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={8}>
                  <Form.Item label="健康检查间隔 (秒)" name="health_check_interval">
                    <InputNumber min={10} max={300} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Divider />
              <Title level={5}>🔄 回放设置</Title>
              <Row gutter={24}>
                <Col xs={24} sm={8}>
                  <Form.Item label="回放速度" name="replay_speed">
                    <InputNumber min={0.1} max={10} step={0.1} precision={1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={saveSystemConfig}>
                保存系统配置
              </Button>
            </Form>
          </Card>
        </div>
      )
    }
  ]

  return (
    <div style={{ padding: '0 0 24px 0' }}>
      <Card.Meta
        title={<span style={{ fontSize: 20, fontWeight: 600 }}>⚙️ 系统配置</span>}
        description={
          <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
            管理风控参数、策略权重、交易所连接和系统设置
          </div>
        }
        style={{ marginBottom: 24 }}
      />
      <Card
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadAllConfigs}>
            重新加载
          </Button>
        }
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabs}
          size="large"
        />
      </Card>
    </div>
  )
}
