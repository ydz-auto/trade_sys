import { useState, useEffect } from 'react'
import { Card, Button, Table, Tag, Modal, Form, Input, Select, Space, Typography, Alert, Empty } from 'antd'
import { PlusOutlined, CameraOutlined, PlayCircleOutlined } from '@ant-design/icons'

const { Title, Text } = Typography
const { Option } = Select
const { TextArea } = Input

const API_BASE = 'http://localhost:8001/api/v1/alpha'

interface Proposal {
  id: string
  name: string
  description?: string
  type: string
  status: string
  created_by: string
  created_at: string
  updated_at: string
  parameters: any
  backtest_results?: any
}

interface Snapshot {
  id: string
  timestamp: string
  name?: string
  type: string
  data: any
  description?: string
}

interface LineageEntry {
  id: string
  factor_type: string
  timestamp: string
  change_type: string
  old_value: any
  new_value: any
  reason: string
  user?: string
  related_proposal_id?: string
}

export function AlphaLifecyclePage() {
  const [activeTab, setActiveTab] = useState('proposals')
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [lineage, setLineage] = useState<LineageEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [proposalsRes, snapshotsRes, lineageRes] = await Promise.all([
        fetch(`${API_BASE}/proposals`),
        fetch(`${API_BASE}/snapshots`),
        fetch(`${API_BASE}/factor-lineage`)
      ])
      
      if (proposalsRes.ok) setProposals(await proposalsRes.json())
      if (snapshotsRes.ok) setSnapshots(await snapshotsRes.json())
      if (lineageRes.ok) setLineage(await lineageRes.json())
    } catch (e) {
      console.error('Failed to fetch data:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateProposal = async (values: any) => {
    try {
      const response = await fetch(`${API_BASE}/proposals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values)
      })
      if (response.ok) {
        setCreateModalVisible(false)
        form.resetFields()
        fetchData()
      }
    } catch (e) {
      console.error('Failed to create proposal:', e)
    }
  }

  const handleCreateSnapshot = async () => {
    try {
      const response = await fetch(`${API_BASE}/snapshots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `Manual Snapshot - ${new Date().toLocaleString()}`,
          type: 'manual',
          description: 'Manually created snapshot'
        })
      })
      if (response.ok) {
        fetchData()
      }
    } catch (e) {
      console.error('Failed to create snapshot:', e)
    }
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      draft: 'default',
      pending_approval: 'blue',
      approved: 'green',
      rejected: 'red',
      deployed: 'purple'
    }
    return colors[status] || 'default'
  }

  const getStatusText = (status: string) => {
    const texts: Record<string, string> = {
      draft: '草稿',
      pending_approval: '待审批',
      approved: '已批准',
      rejected: '已拒绝',
      deployed: '已部署'
    }
    return texts[status] || status
  }

  const getSnapshotTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      auto: 'blue',
      manual: 'green',
      pre_proposal: 'orange',
      post_deploy: 'purple'
    }
    return colors[type] || 'default'
  }

  const getLineageChangeColor = (type: string) => {
    return type === 'weight_update' ? 'blue' : 'orange'
  }

  const proposalColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Proposal) => (
        <div>
          <Text strong>{text}</Text>
          {record.description && <div className="text-xs text-gray-500">{record.description}</div>}
        </div>
      )
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => <Tag>{type}</Tag>
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>
    },
    {
      title: '创建者',
      dataIndex: 'created_by',
      key: 'created_by'
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => new Date(t).toLocaleString()
    },
    {
      title: '操作',
      key: 'actions',
      render: () => (
        <Space>
          <Button type="link" size="small">查看</Button>
          <Button type="link" size="small">编辑</Button>
        </Space>
      )
    }
  ]

  const snapshotColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => <Text className="font-mono text-xs">{id}</Text>
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name'
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (t: string) => <Tag color={getSnapshotTypeColor(t)}>{t}</Tag>
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (t: string) => new Date(t).toLocaleString()
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description'
    },
    {
      title: '操作',
      key: 'actions',
      render: () => (
        <Space>
          <Button type="link" size="small" icon={<PlayCircleOutlined />}>回放</Button>
          <Button type="link" size="small">查看</Button>
        </Space>
      )
    }
  ]

  const lineageColumns = [
    {
      title: '因子',
      dataIndex: 'factor_type',
      key: 'factor_type',
      render: (ft: string) => <Tag color="blue">{ft}</Tag>
    },
    {
      title: '变更类型',
      dataIndex: 'change_type',
      key: 'change_type',
      render: (ct: string) => <Tag color={getLineageChangeColor(ct)}>{ct}</Tag>
    },
    {
      title: '旧值',
      dataIndex: 'old_value',
      key: 'old_value',
      render: (v: any) => JSON.stringify(v)
    },
    {
      title: '新值',
      dataIndex: 'new_value',
      key: 'new_value',
      render: (v: any) => JSON.stringify(v)
    },
    {
      title: '原因',
      dataIndex: 'reason',
      key: 'reason'
    },
    {
      title: '用户',
      dataIndex: 'user',
      key: 'user'
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (t: string) => new Date(t).toLocaleTimeString()
    }
  ]

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <Title level={4}>Alpha Lifecycle</Title>
        <Space>
          {activeTab === 'proposals' && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
              新建提案
            </Button>
          )}
          {activeTab === 'snapshots' && (
            <Button type="primary" icon={<CameraOutlined />} onClick={handleCreateSnapshot}>
              创建快照
            </Button>
          )}
        </Space>
      </div>

      <Card.Meta
        title={<span style={{ fontSize: 16, fontWeight: 600 }}>Alpha Lifecycle System</span>}
        description={
          <div style={{ marginTop: 8, fontSize: 14, color: '#666' }}>
            <p style={{ marginBottom: 4 }}>• 管理策略提案、系统快照和因子变更记录</p>
            <p style={{ marginBottom: 4 }}>• 所有变更都会被追踪，确保可复现性</p>
            <p style={{ marginBottom: 0 }}>• 支持提案审核、回滚和历史版本对比</p>
          </div>
        }
        style={{ marginBottom: 16 }}
      />

      <Card>
        <div className="flex mb-4 gap-2">
          <Button 
            type={activeTab === 'proposals' ? 'primary' : 'default'} 
            onClick={() => setActiveTab('proposals')}
          >
            提案管理
          </Button>
          <Button 
            type={activeTab === 'snapshots' ? 'primary' : 'default'} 
            onClick={() => setActiveTab('snapshots')}
          >
            系统快照
          </Button>
          <Button 
            type={activeTab === 'lineage' ? 'primary' : 'default'} 
            onClick={() => setActiveTab('lineage')}
          >
            因子血缘
          </Button>
        </div>

        {activeTab === 'proposals' && (
          <Table
            dataSource={proposals}
            columns={proposalColumns}
            rowKey="id"
            loading={loading}
            locale={{ emptyText: <Empty description="暂无提案" /> }}
          />
        )}

        {activeTab === 'snapshots' && (
          <Table
            dataSource={snapshots}
            columns={snapshotColumns}
            rowKey="id"
            loading={loading}
            locale={{ emptyText: <Empty description="暂无快照" /> }}
          />
        )}

        {activeTab === 'lineage' && (
          <Table
            dataSource={lineage}
            columns={lineageColumns}
            rowKey="id"
            loading={loading}
            locale={{ emptyText: <Empty description="暂无变更记录" /> }}
          />
        )}
      </Card>

      <Modal
        title="新建提案"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        footer={null}
      >
        <Form form={form} onFinish={handleCreateProposal} layout="vertical">
          <Form.Item
            name="name"
            label="提案名称"
            rules={[{ required: true }]}
          >
            <Input placeholder="输入提案名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} placeholder="描述提案的目的和内容" />
          </Form.Item>
          <Form.Item
            name="type"
            label="类型"
            rules={[{ required: true }]}
          >
            <Select placeholder="选择提案类型">
              <Option value="factor_adjustment">因子调整</Option>
              <Option value="strategy_tweak">策略优化</Option>
              <Option value="weight_change">权重变更</Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">创建提案</Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
