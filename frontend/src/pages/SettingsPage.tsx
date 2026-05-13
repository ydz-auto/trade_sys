import { useState, useEffect } from 'react'
import { Card, Form, Input, InputNumber, Switch, Button, Tabs, Space, Tag, message, Divider, List, Typography } from 'antd'
import { SaveOutlined, ReloadOutlined } from '@ant-design/icons'
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
      label: '🛡️ 风控参数',
      children: (
        <Card title="风控参数配置" style={{ marginTop: 16 }}>
          <Form form={riskForm} layout="vertical" size="small">
            <Divider>仓位限制</Divider>
            <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item label="最大持仓价值 (USDT)" name="max_position_value" style={{ width: 200 }}>
                <InputNumber min={0} step={1000} />
              </Form.Item>
              <Form.Item label="最大持仓数量" name="max_position_count" style={{ width: 150 }}>
                <InputNumber min={1} max={50} />
              </Form.Item>
              <Form.Item label="最大杠杆" name="max_leverage" style={{ width: 150 }}>
                <InputNumber min={1} max={125} />
              </Form.Item>
            </Space>
            
            <Divider>亏损限制</Divider>
            <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item label="日亏损限制 (%)" name="daily_loss_limit_pct" style={{ width: 180 }}>
                <InputNumber min={0} max={50} step={0.5} />
              </Form.Item>
              <Form.Item label="回撤限制 (%)" name="drawdown_limit_pct" style={{ width: 180 }}>
                <InputNumber min={0} max={100} step={1} />
              </Form.Item>
            </Space>
            
            <Divider>订单限制</Divider>
            <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item label="单笔订单限额 (USDT)" name="order_size_limit" style={{ width: 200 }}>
                <InputNumber min={0} step={100} />
              </Form.Item>
              <Form.Item label="交易冷却期 (秒)" name="cooldown_seconds" style={{ width: 180 }}>
                <InputNumber min={0} max={3600} step={10} />
              </Form.Item>
            </Space>
            
            <Divider>止损止盈</Divider>
            <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item label="默认止损 (%)" name="stop_loss_default_pct" style={{ width: 180 }}>
                <InputNumber min={0} max={50} step={0.5} />
              </Form.Item>
              <Form.Item label="默认止盈 (%)" name="take_profit_default_pct" style={{ width: 180 }}>
                <InputNumber min={0} max={100} step={0.5} />
              </Form.Item>
            </Space>
            
            <Divider>黑名单</Divider>
            <Form.Item label="禁止交易的交易对" name="symbol_blacklist">
              <Input.TextArea rows={2} placeholder="用逗号分隔，如: DOGE/USDT,SHIB/USDT" />
            </Form.Item>
            
            <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={saveRiskConfig}>
              保存风控配置
            </Button>
          </Form>
        </Card>
      )
    },
    {
      key: 'strategy',
      label: '⚙️ 策略参数',
      children: (
        <Card title="策略因子权重配置" style={{ marginTop: 16 }}>
          <Form form={strategyForm} layout="vertical" size="small">
            <Title level={5}>因子权重</Title>
            <Text type="secondary">所有权重之和应该等于 1.0</Text>
            <Divider />
            <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item label="趋势权重" name="trend_weight" style={{ width: 150 }}>
                <InputNumber min={0} max={1} step={0.05} precision={2} />
              </Form.Item>
              <Form.Item label="资金流权重" name="flow_weight" style={{ width: 150 }}>
                <InputNumber min={0} max={1} step={0.05} precision={2} />
              </Form.Item>
              <Form.Item label="情绪权重" name="sentiment_weight" style={{ width: 150 }}>
                <InputNumber min={0} max={1} step={0.05} precision={2} />
              </Form.Item>
              <Form.Item label="宏观权重" name="macro_weight" style={{ width: 150 }}>
                <InputNumber min={0} max={1} step={0.05} precision={2} />
              </Form.Item>
            </Space>
            
            <Divider />
            <Title level={5}>信号阈值</Title>
            <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item label="信号触发阈值" name="signal_threshold" style={{ width: 150 }}>
                <InputNumber min={0} max={1} step={0.05} precision={2} />
              </Form.Item>
              <Form.Item label="最低置信度" name="min_confidence" style={{ width: 150 }}>
                <InputNumber min={0} max={1} step={0.05} precision={2} />
              </Form.Item>
            </Space>
            
            <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={saveStrategyConfig}>
              保存策略配置
            </Button>
          </Form>
        </Card>
      )
    },
    {
      key: 'exchange',
      label: '💹 交易所',
      children: (
        <Card title="交易所配置" style={{ marginTop: 16 }}>
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
                      {name.toUpperCase()}
                      <Tag color={config.enabled ? 'green' : 'default'}>
                        {config.enabled ? '已启用' : '已禁用'}
                      </Tag>
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size="small">
                      <Text type="secondary">
                        优先级: {config.priority} | 超时: {config.timeout}s
                      </Text>
                      <Text type="secondary">
                        交易对: {config.symbols.join(', ')}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )
    },
    {
      key: 'system',
      label: '⚡ 系统',
      children: (
        <Card title="系统配置" style={{ marginTop: 16 }}>
          <Form form={systemForm} layout="vertical" size="small">
            <Divider>日志与监控</Divider>
            <Space size="large" style={{ display: 'flex', flexWrap: 'wrap' }}>
              <Form.Item label="日志级别" name="log_level" style={{ width: 150 }}>
                <Input status="warning" />
              </Form.Item>
              <Form.Item label="启用指标采集" name="metrics_enabled" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item label="健康检查间隔 (秒)" name="health_check_interval" style={{ width: 180 }}>
                <InputNumber min={10} max={300} />
              </Form.Item>
            </Space>
            
            <Divider>回放设置</Divider>
            <Form.Item label="回放速度" name="replay_speed" style={{ width: 150 }}>
              <InputNumber min={0.1} max={10} step={0.1} precision={1} />
            </Form.Item>
            
            <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={saveSystemConfig}>
              保存系统配置
            </Button>
          </Form>
        </Card>
      )
    }
  ]

  return (
    <div>
      <Card
        title="⚙️ 系统配置"
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
