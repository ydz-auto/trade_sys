# 多数据源价格集成文档

## 📋 概述

前端已集成多数据源价格对比功能，支持同时显示多个交易所的同一交易对价格。

## 🎯 功能特性

- ✅ **多交易所支持**: Binance, CoinGecko, OKX
- ✅ **实时价格对比**: 显示各交易所价格差异
- ✅ **熔断器状态**: 显示各数据源的健康状态
- ✅ **自动降级**: 某个数据源失败时自动切换
- ✅ **定时刷新**: 可配置的自动刷新间隔

## 📦 新增文件

### 类型定义
- `src/types/index.ts` - 新增 `ExchangePrice`, `PriceComparison`, `PriceSourceStatus` 类型

### API 服务
- `src/services/api/tradingApi.ts` - 新增多数据源 API 函数

### React Hooks
- `src/hooks/useMultiSourcePrices.ts` - 多数据源价格 Hook

### 组件
- `src/components/MultiSourcePriceCard.tsx` - 多数据源价格卡片组件

## 🔌 API 函数

### 1. 获取所有数据源价格

```typescript
import { fetchPricesFromAllSources } from './services/api/tradingApi'

// 获取 BTC, ETH, SOL 在所有交易所的价格
const prices = await fetchPricesFromAllSources('BTC,ETH,SOL')

// 返回数据示例
[
  { symbol: 'BTC/USDT', price: 81018.18, change24h: -0.20, exchange: 'binance' },
  { symbol: 'BTC/USDT', price: 81000.00, change24h: -0.20, exchange: 'coingecko' },
  { symbol: 'BTC/USDT', price: 81015.20, change24h: 0.00, exchange: 'okx' },
  // ... ETH, SOL 的数据
]
```

### 2. 获取价格对比分析

```typescript
import { fetchPriceComparison } from './services/api/tradingApi'

// 获取 BTC 的价格对比
const comparison = await fetchPriceComparison('BTC')

// 返回数据示例
{
  symbol: 'BTC/USDT',
  prices: [
    { exchange: 'binance', price: 81018.18, change24h: -0.20, volume24h: 966464900, latencyMs: 586 },
    { exchange: 'coingecko', price: 81000.00, change24h: -0.20, volume24h: 31609042937, latencyMs: 610 },
    { exchange: 'okx', price: 81015.20, change24h: 0.00, volume24h: 940010508, latencyMs: 721 }
  ],
  priceSpread: 0.0224,  // 价差百分比
  bestBid: 'binance',   // 最高价格（适合卖出）
  bestAsk: 'coingecko', // 最低价格（适合买入）
  timestamp: '2026-05-13T11:24:28.934284'
}
```

### 3. 获取数据源状态

```typescript
import { fetchPriceSourcesStatus } from './services/api/tradingApi'

const status = await fetchPriceSourcesStatus()

// 返回数据示例
{
  binance: {
    name: 'Binance',
    priority: 1,
    circuitBreaker: { state: 'closed', failureCount: 0 },
    status: { available: true, latencyMs: 586, lastSuccess: '...' }
  },
  coingecko: { ... },
  okx: { ... }
}
```

## 🪝 React Hook

### useMultiSourcePrices

```typescript
import { useMultiSourcePrices } from './hooks'

function MyComponent() {
  const {
    prices,        // 所有交易所的价格数据
    comparison,    // 价格对比分析
    sourceStatus,  // 数据源状态
    isLoading,     // 加载状态
    error,         // 错误信息
    lastUpdate,    // 最后更新时间
    refetch        // 手动刷新函数
  } = useMultiSourcePrices({
    symbols: 'BTC,ETH,SOL',  // 交易对列表
    refreshInterval: 5000,   // 刷新间隔（毫秒）
    enabled: true            // 是否启用自动刷新
  })

  // 按交易对分组显示
  const btcPrices = prices.filter(p => p.symbol.includes('BTC'))
  const ethPrices = prices.filter(p => p.symbol.includes('ETH'))

  return (
    <div>
      {isLoading && <Spin />}
      {error && <Alert message={error} type="error" />}
      
      {/* 显示 BTC 各交易所价格 */}
      {btcPrices.map(price => (
        <div key={price.exchange}>
          {price.exchange}: ${price.price}
        </div>
      ))}
      
      {/* 显示价差 */}
      {comparison && (
        <div>价差: {comparison.priceSpread}%</div>
      )}
    </div>
  )
}
```

## 🧩 组件使用

### MultiSourcePriceCard

```typescript
import { MultiSourcePriceCard } from './components'

function Dashboard() {
  return (
    <div>
      {/* 显示 BTC 多交易所价格 */}
      <MultiSourcePriceCard 
        symbol="BTC" 
        refreshInterval={5000} 
      />
      
      {/* 显示 ETH 多交易所价格 */}
      <MultiSourcePriceCard 
        symbol="ETH" 
        refreshInterval={10000}
      />
    </div>
  )
}
```

## 📊 后端 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/prices?all_sources=true` | GET | 获取所有交易所的同一交易对价格 |
| `/api/v1/prices/compare?symbol=BTC` | GET | 获取指定交易对的价格对比分析 |
| `/api/v1/prices/sources` | GET | 获取所有数据源的状态 |

## 🔧 配置说明

### 环境变量

```env
# 是否使用模拟数据
VITE_USE_MOCK_API=false

# API 基础地址
VITE_API_BASE_URL=/api/v1
```

### 熔断器配置

后端为每个数据源配置了独立的熔断器：

```python
CircuitBreakerConfig(
    name="price_binance",
    failure_threshold=3,      # 连续失败3次后熔断
    recovery_timeout=60.0,    # 60秒后尝试恢复
    half_open_max_calls=2     # 半开状态最多允许2次测试
)
```

## 🎨 界面展示

MultiSourcePriceCard 组件显示：

1. **交易所列表** - Binance, CoinGecko, OKX
2. **实时价格** - 各交易所当前价格
3. **24h变化** - 涨跌幅
4. **API延迟** - 响应时间
5. **熔断状态** - 正常/熔断/恢复中
6. **价差提示** - 最高/最低价格标记
7. **操作建议** - 最佳买入/卖出交易所

## 📝 示例代码

### 在 DashboardPage 中使用

```typescript
import { MultiSourcePriceCard } from '../components'
import { useMultiSourcePrices } from '../hooks'

export function DashboardPage() {
  // 使用 Hook 获取数据
  const { prices, comparison, isLoading } = useMultiSourcePrices({
    symbols: 'BTC,ETH,SOL',
    refreshInterval: 5000
  })

  return (
    <div>
      {/* 方式1: 使用现成组件 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <MultiSourcePriceCard symbol="BTC" />
        </Col>
        <Col xs={24} md={12}>
          <MultiSourcePriceCard symbol="ETH" />
        </Col>
      </Row>

      {/* 方式2: 自定义显示 */}
      <div>
        {prices.filter(p => p.symbol.includes('BTC')).map(price => (
          <div key={price.exchange}>
            {price.exchange}: ${price.price}
          </div>
        ))}
      </div>
    </div>
  )
}
```

## ✅ 测试验证

启动前端后，访问 http://localhost:3000，你应该能看到：

1. BTC/USDT 各交易所价格对比卡片
2. ETH/USDT 各交易所价格对比卡片
3. 实时更新的价格和状态
4. 价差提示和操作建议

## 🐛 故障排除

### 价格不更新
- 检查后端服务是否运行: `curl http://localhost:8001/health`
- 检查网络连接
- 查看浏览器控制台是否有 CORS 错误

### 某个数据源显示错误
- 这是正常的熔断机制
- 系统会自动切换到其他可用数据源
- 等待 60 秒后熔断器会尝试恢复

### 所有数据源都失败
- 检查网络连接
- 查看后端日志: `tail -f /tmp/api_final.log`
- 系统会返回降级数据（模拟价格）
