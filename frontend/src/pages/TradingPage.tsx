import React, { useState, useEffect } from 'react';
import { tradingApi } from '../services/api/tradingApiService';

interface TradingState {
  positions: any[];
  orders: any[];
  status: any;
  accounts: any[];
}

export const TradingPage: React.FC = () => {
  const [state, setState] = useState<TradingState>({
    positions: [],
    orders: [],
    status: null,
    accounts: []
  });
  const [loading, setLoading] = useState(false);
  const [orderForm, setOrderForm] = useState({
    symbol: 'BTC/USDT',
    side: 'buy' as 'buy' | 'sell',
    quantity: 0.01,
    exchange: 'binance' as 'binance' | 'okx',
    market_type: 'usdt_futures' as 'spot' | 'usdt_futures' | 'coin_futures',
    leverage: 5,
    position_size_pct: 10,
    stop_loss_pct: 2,
    take_profit_pct: 5,
  });

  const bgColor = 'bg-gray-900';
  const cardBg = 'bg-gray-800';
  const textColor = 'text-white';
  const subTextColor = 'text-gray-400';
  const borderColor = 'border-gray-700';
  const theme = 'dark';

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [positions, orders, status, accounts] = await Promise.all([
        tradingApi.getPositions(),
        tradingApi.getOrders(),
        tradingApi.getStatus(),
        tradingApi.getAccounts()
      ]);
      setState({ positions, orders, status, accounts: accounts?.accounts || [] });
    } catch (error) {
      console.error('Failed to fetch trading data:', error);
    }
  };

  const handlePlaceOrder = async () => {
    setLoading(true);
    try {
      await tradingApi.placeOrder(orderForm);
      await fetchData();
    } catch (error) {
      console.error('Failed to place order:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleClosePosition = async (symbol: string) => {
    try {
      await tradingApi.closePosition(symbol);
      await fetchData();
    } catch (error) {
      console.error('Failed to close position:', error);
    }
  };

  const handleSetLeverage = async (symbol: string, leverage: number) => {
    try {
      await tradingApi.setLeverage(symbol, leverage);
      await fetchData();
    } catch (error) {
      console.error('Failed to set leverage:', error);
    }
  };

  const handleSetSLTP = async (symbol: string, sl?: number, tp?: number) => {
    try {
      await tradingApi.setStopLossTakeProfit(symbol, sl, tp);
      await fetchData();
    } catch (error) {
      console.error('Failed to set SL/TP:', error);
    }
  };

  return (
    <div className={`min-h-screen ${bgColor} p-6`}>
      <div className="max-w-7xl mx-auto space-y-6">
        <h1 className={`text-3xl font-bold ${textColor}`}>实盘交易</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className={`${cardBg} rounded-xl p-6 border ${borderColor}`}>
            <h2 className={`text-xl font-semibold ${textColor} mb-4`}>下单</h2>
            <div className="space-y-4">
              <div>
                <label className={`block text-sm ${subTextColor} mb-1`}>交易所</label>
                <select
                  value={orderForm.exchange}
                  onChange={(e) => setOrderForm({...orderForm, exchange: e.target.value as any})}
                  className={`w-full px-3 py-2 rounded-lg border ${borderColor} ${bgColor} ${textColor}`}
                >
                  <option value="binance">Binance</option>
                  <option value="okx">OKX</option>
                </select>
              </div>

              <div>
                <label className={`block text-sm ${subTextColor} mb-1`}>市场类型</label>
                <select
                  value={orderForm.market_type}
                  onChange={(e) => setOrderForm({...orderForm, market_type: e.target.value as any})}
                  className={`w-full px-3 py-2 rounded-lg border ${borderColor} ${bgColor} ${textColor}`}
                >
                  <option value="spot">现货 (Spot)</option>
                  <option value="usdt_futures">USDT合约 (Futures)</option>
                  <option value="coin_futures">币本位合约</option>
                </select>
              </div>

              <div>
                <label className={`block text-sm ${subTextColor} mb-1`}>交易对</label>
                <select
                  value={orderForm.symbol}
                  onChange={(e) => setOrderForm({...orderForm, symbol: e.target.value})}
                  className={`w-full px-3 py-2 rounded-lg border ${borderColor} ${bgColor} ${textColor}`}
                >
                  <option value="BTC/USDT">BTC/USDT</option>
                  <option value="ETH/USDT">ETH/USDT</option>
                  <option value="SOL/USDT">SOL/USDT</option>
                </select>
              </div>

              <div className="flex gap-4">
                <button
                  onClick={() => setOrderForm({...orderForm, side: 'buy'})}
                  className={`flex-1 py-3 rounded-lg font-semibold transition ${
                    orderForm.side === 'buy'
                      ? 'bg-green-500 text-white'
                      : `${bgColor} ${textColor} border ${borderColor}`
                  }`}
                >
                  买入 (Long)
                </button>
                <button
                  onClick={() => setOrderForm({...orderForm, side: 'sell'})}
                  className={`flex-1 py-3 rounded-lg font-semibold transition ${
                    orderForm.side === 'sell'
                      ? 'bg-red-500 text-white'
                      : `${bgColor} ${textColor} border ${borderColor}`
                  }`}
                >
                  卖出 (Short)
                </button>
              </div>

              <div>
                <label className={`block text-sm ${subTextColor} mb-1`}>数量</label>
                <input
                  type="number"
                  step="0.001"
                  value={orderForm.quantity}
                  onChange={(e) => setOrderForm({...orderForm, quantity: parseFloat(e.target.value)})}
                  className={`w-full px-3 py-2 rounded-lg border ${borderColor} ${bgColor} ${textColor}`}
                />
              </div>

              {orderForm.market_type !== 'spot' && (
                <>
                  <div>
                    <label className={`block text-sm ${subTextColor} mb-1`}>杠杆 ({orderForm.leverage}x)</label>
                    <input
                      type="range"
                      min="1"
                      max="20"
                      value={orderForm.leverage}
                      onChange={(e) => setOrderForm({...orderForm, leverage: parseInt(e.target.value)})}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>1x</span>
                      <span>20x</span>
                    </div>
                  </div>

                  <div>
                    <label className={`block text-sm ${subTextColor} mb-1`}>仓位比例 ({orderForm.position_size_pct}%)</label>
                    <input
                      type="range"
                      min="5"
                      max="100"
                      step="5"
                      value={orderForm.position_size_pct}
                      onChange={(e) => setOrderForm({...orderForm, position_size_pct: parseInt(e.target.value)})}
                      className="w-full"
                    />
                  </div>
                </>
              )}

              {orderForm.market_type !== 'spot' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className={`block text-sm ${subTextColor} mb-1`}>止损 (%)</label>
                      <input
                        type="number"
                        step="0.1"
                        value={orderForm.stop_loss_pct}
                        onChange={(e) => setOrderForm({...orderForm, stop_loss_pct: parseFloat(e.target.value)})}
                        className={`w-full px-3 py-2 rounded-lg border ${borderColor} ${bgColor} ${textColor}`}
                      />
                    </div>
                    <div>
                      <label className={`block text-sm ${subTextColor} mb-1`}>止盈 (%)</label>
                      <input
                        type="number"
                        step="0.1"
                        value={orderForm.take_profit_pct}
                        onChange={(e) => setOrderForm({...orderForm, take_profit_pct: parseFloat(e.target.value)})}
                        className={`w-full px-3 py-2 rounded-lg border ${borderColor} ${bgColor} ${textColor}`}
                      />
                    </div>
                  </div>
                </>
              )}

              <button
                onClick={handlePlaceOrder}
                disabled={loading}
                className={`w-full py-3 rounded-lg font-semibold transition ${
                  orderForm.side === 'buy'
                    ? 'bg-green-500 hover:bg-green-600 text-white'
                    : 'bg-red-500 hover:bg-red-600 text-white'
                } disabled:opacity-50`}
              >
                {loading ? '处理中...' : `市价${orderForm.side === 'buy' ? '买入' : '卖出'} ${orderForm.market_type === 'spot' ? '现货' : '合约'}`}
              </button>
            </div>
          </div>

          <div className={`${cardBg} rounded-xl p-6 border ${borderColor}`}>
            <h2 className={`text-xl font-semibold ${textColor} mb-4`}>账户概览</h2>
            {state.status && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
                    <div className={subTextColor}>总权益</div>
                    <div className={`text-2xl font-bold ${textColor}`}>
                      ${state.status.total_equity?.toFixed(2)}
                    </div>
                  </div>
                  <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
                    <div className={subTextColor}>可用余额</div>
                    <div className={`text-2xl font-bold ${textColor}`}>
                      ${state.status.available_balance?.toFixed(2)}
                    </div>
                  </div>
                  <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
                    <div className={subTextColor}>浮动盈亏</div>
                    <div className={`text-2xl font-bold ${
                      state.status.total_unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      ${state.status.total_unrealized_pnl?.toFixed(2)}
                    </div>
                  </div>
                  <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
                    <div className={subTextColor}>已实现盈亏</div>
                    <div className={`text-2xl font-bold ${
                      state.status.total_realized_pnl >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      ${state.status.total_realized_pnl?.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
                  <div className={subTextColor}>交易模式</div>
                  <div className={`text-lg font-semibold ${textColor}`}>
                    {state.status.mode === 'auto' ? '🤖 自动' : state.status.mode === 'manual' ? '👤 手动' : '🔄 混合'}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className={`${cardBg} rounded-xl p-6 border ${borderColor}`}>
            <h2 className={`text-xl font-semibold ${textColor} mb-4`}>账户详情</h2>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {state.accounts.map((acc: any, i: number) => (
                <div key={i} className={`p-3 rounded-lg ${theme === 'dark' ? 'bg-gray-700' : 'bg-gray-100'}`}>
                  <div className="flex justify-between items-center mb-2">
                    <span className={`font-semibold ${textColor}`}>
                      {acc.exchange?.toUpperCase()} {acc.market_type === 'spot' ? '现货' : '合约'}
                    </span>
                    <span className={`text-xs px-2 py-1 rounded ${
                      theme === 'dark' ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600'
                    }`}>
                      {acc.market_type}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className={subTextColor}>余额: <span className={textColor}>${acc.balance?.toFixed(2)}</span></div>
                    <div className={subTextColor}>可用: <span className={textColor}>${acc.available_balance?.toFixed(2)}</span></div>
                    <div className={subTextColor}>保证金: <span className={textColor}>${acc.margin_balance?.toFixed(2)}</span></div>
                    <div className={subTextColor}>持仓: <span className={textColor}>{acc.positions_count}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className={`${cardBg} rounded-xl p-6 border ${borderColor}`}>
          <h2 className={`text-xl font-semibold ${textColor} mb-4`}>当前持仓</h2>
          {state.positions.length === 0 ? (
            <div className={`text-center py-8 ${subTextColor}`}>暂无持仓</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className={`${subTextColor} text-left text-sm`}>
                    <th className="pb-3">交易对</th>
                    <th className="pb-3">交易所</th>
                    <th className="pb-3">类型</th>
                    <th className="pb-3">方向</th>
                    <th className="pb-3">数量</th>
                    <th className="pb-3">杠杆</th>
                    <th className="pb-3">开仓价</th>
                    <th className="pb-3">当前价</th>
                    <th className="pb-3">浮动盈亏</th>
                    <th className="pb-3">止损/止盈</th>
                    <th className="pb-3">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {state.positions.map((pos: any, i: number) => (
                    <tr key={i} className={`border-t ${borderColor}`}>
                      <td className={`py-3 ${textColor}`}>{pos.symbol}</td>
                      <td className={`py-3 ${subTextColor}`}>{pos.exchange}</td>
                      <td className={`py-3 ${subTextColor}`}>{pos.market_type === 'spot' ? '现货' : '合约'}</td>
                      <td className={`py-3 ${pos.side === 'long' ? 'text-green-500' : 'text-red-500'}`}>
                        {pos.side === 'long' ? '多' : '空'}
                      </td>
                      <td className={`py-3 ${textColor}`}>{pos.quantity}</td>
                      <td className={`py-3 ${textColor}`}>{pos.leverage}x</td>
                      <td className={`py-3 ${textColor}`}>${pos.entry_price?.toFixed(2)}</td>
                      <td className={`py-3 ${textColor}`}>${pos.current_price?.toFixed(2)}</td>
                      <td className={`py-3 ${pos.unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        ${pos.unrealized_pnl?.toFixed(2)} ({pos.unrealized_pnl_pct ? (pos.unrealized_pnl_pct * 100).toFixed(2) : 0}%)
                      </td>
                      <td className={`py-3 text-sm ${subTextColor}`}>
                        {pos.stop_loss_price && <span>SL: ${pos.stop_loss_price?.toFixed(0)} </span>}
                        {pos.take_profit_price && <span>TP: ${pos.take_profit_price?.toFixed(0)}</span>}
                        {!pos.stop_loss_price && !pos.take_profit_price && '-'}
                      </td>
                      <td className="py-3">
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSetLeverage(pos.symbol, pos.leverage === 5 ? 10 : 5)}
                            className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
                          >
                            {pos.leverage}x → {pos.leverage === 5 ? '10' : '5'}x
                          </button>
                          <button
                            onClick={() => handleSetSLTP(pos.symbol, 2, 5)}
                            className="px-2 py-1 text-xs bg-yellow-500 text-white rounded hover:bg-yellow-600"
                          >
                            SL/TP
                          </button>
                          <button
                            onClick={() => handleClosePosition(pos.symbol)}
                            className="px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600"
                          >
                            平仓
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className={`${cardBg} rounded-xl p-6 border ${borderColor}`}>
          <h2 className={`text-xl font-semibold ${textColor} mb-4`}>订单历史</h2>
          {state.orders.length === 0 ? (
            <div className={`text-center py-8 ${subTextColor}`}>暂无订单</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className={`${subTextColor} text-left text-sm`}>
                    <th className="pb-3">订单ID</th>
                    <th className="pb-3">交易对</th>
                    <th className="pb-3">交易所</th>
                    <th className="pb-3">类型</th>
                    <th className="pb-3">方向</th>
                    <th className="pb-3">数量</th>
                    <th className="pb-3">杠杆</th>
                    <th className="pb-3">状态</th>
                    <th className="pb-3">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {state.orders.slice(0, 10).map((order: any) => (
                    <tr key={order.order_id} className={`border-t ${borderColor}`}>
                      <td className={`py-3 ${textColor} font-mono text-xs`}>{order.order_id}</td>
                      <td className={`py-3 ${textColor}`}>{order.symbol}</td>
                      <td className={`py-3 ${subTextColor}`}>{order.exchange}</td>
                      <td className={`py-3 ${subTextColor}`}>{order.market_type === 'spot' ? '现货' : '合约'}</td>
                      <td className={`py-3 ${order.side === 'buy' ? 'text-green-500' : 'text-red-500'}`}>
                        {order.side === 'buy' ? '买入' : '卖出'}
                      </td>
                      <td className={`py-3 ${textColor}`}>{order.quantity}</td>
                      <td className={`py-3 ${textColor}`}>{order.leverage}x</td>
                      <td className={`py-3`}>
                        <span className={`px-2 py-1 rounded text-xs ${
                          order.status === 'filled'
                            ? 'bg-green-500/20 text-green-500'
                            : order.status === 'pending'
                            ? 'bg-yellow-500/20 text-yellow-500'
                            : 'bg-gray-500/20 text-gray-500'
                        }`}>
                          {order.status === 'filled' ? '已成交' : order.status === 'pending' ? '处理中' : order.status}
                        </span>
                      </td>
                      <td className={`py-3 ${subTextColor}`}>
                        {new Date(order.created_at).toLocaleString('zh-CN')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
