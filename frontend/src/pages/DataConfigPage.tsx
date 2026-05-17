import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, Switch, Space, Tag, Popconfirm, message, Tabs, InputNumber, Divider, Alert, Typography } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import { configApi } from '../services/api/configApiService'
import type { NewsSource, CreateNewsSource, UpdateNewsSource, ApiKey, CreateApiKey, UpdateApiKey, LlmConfig, LlmProvider } from '../services/api/configApi'

const { Text } = Typography

export function DataConfigPage() {
  const [activeTab, setActiveTab] = useState('news')
  const [loading, setLoading] = useState(false)
  const [newsSources, setNewsSources] = useState<NewsSource[]>([])
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null)

  const [newsModalVisible, setNewsModalVisible] = useState(false)
  const [newsModalMode, setNewsModalMode] = useState<'create' | 'edit'>('create')
  const [newsForm] = Form.useForm()
  const [currentNewsSource, setCurrentNewsSource] = useState<NewsSource | null>(null)

  const [apiKeyModalVisible, setApiKeyModalVisible] = useState(false)
  const [apiKeyModalMode, setApiKeyModalMode] = useState<'create' | 'edit'>('create')
  const [apiKeyForm] = Form.useForm()
  const [currentApiKey, setCurrentApiKey] = useState<ApiKey | null>(null)

  useEffect(() => {
    loadAllData()
  }, [])

  const loadAllData = async () => {
    setLoading(true)
    try {
      await Promise.all([
        loadNewsSources(),
        loadApiKeys(),
        loadLlmConfig(),
      ])
    } catch (error) {
      message.error('加载配置失败')
    } finally {
      setLoading(false)
    }
  }

  const loadNewsSources = async () => {
    try {
      const res = await configApi.listNewsSources()
      setNewsSources(res.sources)
    } catch (error) {
      console.error('Failed to load news sources:', error)
    }
  }

  const loadApiKeys = async () => {
    try {
      const res = await configApi.listApiKeys()
      setApiKeys(res.keys)
    } catch (error) {
      console.error('Failed to load API keys:', error)
    }
  }

  const loadLlmConfig = async () => {
    try {
      const res = await configApi.getLlmConfig()
      setLlmConfig(res)
    } catch (error) {
      console.error('Failed to load LLM config:', error)
    }
  }

  // News Source handlers
  const openNewsModal = (mode: 'create' | 'edit', source?: NewsSource) => {
    setNewsModalMode(mode)
    if (mode === 'edit' && source) {
      setCurrentNewsSource(source)
      newsForm.setFieldsValue({
        name: source.name,
        type: source.type,
        url: source.url,
        enabled: source.enabled,
        priority: source.priority,
        keywords: source.keywords.join(', '),
        blacklist: source.blacklist.join(', '),
        update_interval: source.update_interval,
      })
    } else {
      setCurrentNewsSource(null)
      newsForm.resetFields()
      newsForm.setFieldsValue({
        enabled: true,
        priority: 1,
        keywords: 'bitcoin, btc, crypto, ethereum',
        update_interval: 300,
      })
    }
    setNewsModalVisible(true)
  }

  const handleNewsSubmit = async () => {
    try {
      const values = await newsForm.validateFields()
      const data: CreateNewsSource | UpdateNewsSource = {
        name: values.name,
        type: values.type,
        url: values.url,
        enabled: values.enabled,
        priority: values.priority,
        keywords: values.keywords.split(',').map((k: string) => k.trim()).filter(Boolean),
        blacklist: values.blacklist.split(',').map((k: string) => k.trim()).filter(Boolean),
        update_interval: values.update_interval,
      }

      if (newsModalMode === 'create') {
        await configApi.createNewsSource(data as CreateNewsSource)
        message.success('新闻源创建成功')
      } else if (currentNewsSource) {
        await configApi.updateNewsSource(currentNewsSource.id, data as UpdateNewsSource)
        message.success('新闻源更新成功')
      }

      setNewsModalVisible(false)
      newsForm.resetFields()
      loadNewsSources()
    } catch (error) {
      message.error('操作失败')
    }
  }

  const handleNewsDelete = async (id: string) => {
    try {
      await configApi.deleteNewsSource(id)
      message.success('删除成功')
      loadNewsSources()
    } catch (error) {
      message.error('删除失败')
    }
  }

  // API Key handlers
  const openApiKeyModal = (mode: 'create' | 'edit', key?: ApiKey) => {
    setApiKeyModalMode(mode)
    if (mode === 'edit' && key) {
      setCurrentApiKey(key)
      apiKeyForm.setFieldsValue({
        name: key.name,
        type: key.type,
        provider: key.provider,
        enabled: key.enabled,
      })
    } else {
      setCurrentApiKey(null)
      apiKeyForm.resetFields()
      apiKeyForm.setFieldsValue({
        enabled: true,
      })
    }
    setApiKeyModalVisible(true)
  }

  const handleApiKeySubmit = async () => {
    try {
      const values = await apiKeyForm.validateFields()

      if (apiKeyModalMode === 'create') {
        if (!values.api_key) {
          message.error('请输入 API Key')
          return
        }
        const data: CreateApiKey = {
          name: values.name,
          type: values.type,
          provider: values.provider,
          api_key: values.api_key,
          secret: values.secret,
          enabled: values.enabled,
        }
        await configApi.createApiKey(data)
        message.success('API Key 创建成功')
      } else if (currentApiKey) {
        const data: UpdateApiKey = {
          name: values.name,
          enabled: values.enabled,
        }
        if (values.api_key) {
          data.api_key = values.api_key
        }
        if (values.secret) {
          data.secret = values.secret
        }
        await configApi.updateApiKey(currentApiKey.id, data)
        message.success('API Key 更新成功')
      }

      setApiKeyModalVisible(false)
      apiKeyForm.resetFields()
      loadApiKeys()
    } catch (error) {
      message.error('操作失败')
    }
  }

  const handleApiKeyDelete = async (id: string) => {
    try {
      await configApi.deleteApiKey(id)
      message.success('删除成功')
      loadApiKeys()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const newsColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => <Tag color="blue">{type.toUpperCase()}</Tag>,
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      ellipsis: true,
      width: 200,
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'default'}>
          {status === 'active' ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      render: (keywords: string[]) => (
        <Space size={[0, 4]} wrap>
          {keywords.slice(0, 3).map(k => (
            <Tag key={k}>{k}</Tag>
          ))}
          {keywords.length > 3 && <Tag>+{keywords.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: NewsSource) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openNewsModal('edit', record)}
          />
          <Popconfirm
            title="确认删除？"
            onConfirm={() => handleNewsDelete(record.id)}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const apiKeyColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => <Tag color="purple">{type.toUpperCase()}</Tag>,
    },
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
    },
    {
      title: 'Key',
      dataIndex: 'key_hint',
      key: 'key_hint',
      render: (hint: string) => <Text code>{hint}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean) => (
        enabled ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : <ExclamationCircleOutlined style={{ color: '#faad14' }} />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: ApiKey) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openApiKeyModal('edit', record)}
          />
          <Popconfirm
            title="确认删除？"
            onConfirm={() => handleApiKeyDelete(record.id)}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const tabItems = [
    {
      key: 'news',
      label: '📰 新闻源',
      children: (
        <Card
          title="新闻源管理"
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} onClick={loadNewsSources}>刷新</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => openNewsModal('create')}>
                添加新闻源
              </Button>
            </Space>
          }
        >
          <Alert
            message="新闻源配置"
            description="配置要采集的新闻源，支持 RSS 订阅和 API 接口。关键词和黑名单用于过滤相关内容。"
            type="info"
            style={{ marginBottom: 16 }}
          />
          <Table
            dataSource={newsSources}
            columns={newsColumns}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 10 }}
          />
        </Card>
      ),
    },
    {
      key: 'api-keys',
      label: '🔑 API Keys',
      children: (
        <Card
          title="API Keys 管理"
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} onClick={loadApiKeys}>刷新</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => openApiKeyModal('create')}>
                添加 API Key
              </Button>
            </Space>
          }
        >
          <Alert
            message="API Key 安全说明"
            description="API Keys 加密存储，仅显示前4后4位字符。支持 LLM、交易所、数据源三类 Key。"
            type="warning"
            style={{ marginBottom: 16 }}
          />
          <Table
            dataSource={apiKeys}
            columns={apiKeyColumns}
            rowKey="id"
            loading={loading}
            pagination={{ pageSize: 10 }}
          />
        </Card>
      ),
    },
    {
      key: 'llm',
      label: '🤖 LLM 配置',
      children: (
        <Card title="LLM 提供商配置">
          <Alert
            message="LLM 多级降级配置"
            description={
              <div>
                <p>当前降级链: 智谱AI → 硅基流动 → DeepSeek → 百度千帆 → 阿里百炼 → Ollama本地 → 关键词匹配</p>
                <p>请在环境变量中设置对应的 API Key，或在 API Keys 页面添加。</p>
              </div>
            }
            type="info"
            style={{ marginBottom: 16 }}
          />
          {llmConfig && (
            <div>
              <Divider>已配置提供商</Divider>
              {llmConfig.providers.map((provider: LlmProvider, index: number) => (
                <Card key={provider.name} size="small" style={{ marginBottom: 8 }}>
                  <Space>
                    <Tag color={provider.enabled ? 'green' : 'default'}>
                      #{index + 1}
                    </Tag>
                    <Text strong>{provider.name}</Text>
                    <Tag>{provider.provider}</Tag>
                    <Text type="secondary">{provider.base_url}</Text>
                  </Space>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">模型: </Text>
                    {provider.models.map(m => <Tag key={m}>{m}</Tag>)}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>
      ),
    },
  ]

  return (
    <div>
      <Card
        title="📊 数据源配置"
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadAllData}>
            刷新全部
          </Button>
        }
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
      </Card>

      {/* News Source Modal */}
      <Modal
        title={newsModalMode === 'create' ? '添加新闻源' : '编辑新闻源'}
        open={newsModalVisible}
        onOk={handleNewsSubmit}
        onCancel={() => {
          setNewsModalVisible(false)
          newsForm.resetFields()
        }}
        width={600}
      >
        <Form form={newsForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如: CoinDesk RSS" />
          </Form.Item>
          <Space style={{ display: 'flex' }}>
            <Form.Item name="type" label="类型" rules={[{ required: true }]} style={{ width: 150 }}>
              <Select>
                <Select.Option value="rss">RSS</Select.Option>
                <Select.Option value="api">API</Select.Option>
                <Select.Option value="website">Website</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="priority" label="优先级" rules={[{ required: true }]} style={{ width: 100 }}>
              <InputNumber min={1} max={10} />
            </Form.Item>
            <Form.Item name="enabled" label="启用" valuePropName="checked" style={{ width: 80 }}>
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item name="url" label="URL" rules={[{ required: true }]}>
            <Input placeholder="https://example.com/rss.xml" />
          </Form.Item>
          <Form.Item name="keywords" label="关键词 (逗号分隔)">
            <Input placeholder="bitcoin, btc, crypto, ethereum" />
          </Form.Item>
          <Form.Item name="blacklist" label="黑名单关键词 (逗号分隔)">
            <Input placeholder="ads, sponsored, advertisement" />
          </Form.Item>
          <Form.Item name="update_interval" label="更新间隔 (秒)">
            <InputNumber min={60} max={3600} defaultValue={300} />
          </Form.Item>
        </Form>
      </Modal>

      {/* API Key Modal */}
      <Modal
        title={apiKeyModalMode === 'create' ? '添加 API Key' : '编辑 API Key'}
        open={apiKeyModalVisible}
        onOk={handleApiKeySubmit}
        onCancel={() => {
          setApiKeyModalVisible(false)
          apiKeyForm.resetFields()
        }}
        width={500}
      >
        <Form form={apiKeyForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如: 智谱AI Key" />
          </Form.Item>
          <Space style={{ display: 'flex' }}>
            <Form.Item name="type" label="类型" rules={[{ required: true }]} style={{ width: 150 }}>
              <Select>
                <Select.Option value="llm">LLM</Select.Option>
                <Select.Option value="exchange">交易所</Select.Option>
                <Select.Option value="data">数据源</Select.Option>
                <Select.Option value="other">其他</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="provider" label="提供商" rules={[{ required: true }]} style={{ width: 150 }}>
              <Input placeholder="如: zhipu" />
            </Form.Item>
          </Space>
          {apiKeyModalMode === 'create' && (
            <>
              <Form.Item name="api_key" label="API Key" rules={[{ required: true }]}>
                <Input.Password placeholder="输入完整 API Key" />
              </Form.Item>
              <Form.Item name="secret" label="Secret (可选)">
                <Input.Password placeholder="如有 Secret 请输入" />
              </Form.Item>
            </>
          )}
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
