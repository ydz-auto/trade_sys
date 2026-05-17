# TradeLab API Documentation

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently no authentication required (development mode).

## Endpoints

### Health

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "mock_mode": true,
  "timestamp": "2024-01-01T00:00:00"
}
```

---

### Dashboard

#### GET /dashboard

Get trading dashboard data from Projection.

**Response:**
```json
{
  "prices": [...],
  "compositeScore": 0.65,
  "regime": {...},
  "risk": {...},
  "signal": {...},
  "factors": [...],
  "positions": [...],
  "news": [...],
  "weightVersions": [...],
  "dataSources": [...],
  "traders": [...],
  "socialPosts": [...],
  "macro": {...},
  "fearGreed": {...},
  "etf": {...}
}
```

---

### Projection (Runtime State)

#### GET /projection/dashboard

Get Dashboard state from Projection.

#### GET /projection/prices

Get prices list.

#### GET /projection/signals

Get signals.

**Query Parameters:**
- `symbol` (optional): Filter by symbol

#### GET /projection/decision/latest

Get latest decision.

**Query Parameters:**
- `symbol` (optional): Filter by symbol

#### GET /projection/decision/history

Get decision history.

**Query Parameters:**
- `symbol` (optional): Filter by symbol
- `limit` (optional): Number of results (default: 20)

#### GET /projection/decision/stats

Get decision statistics.

#### GET /projection/risk/state

Get risk state.

#### GET /projection/risk/level

Get risk level.

#### GET /projection/risk/daily

Get daily risk metrics.

#### GET /projection/position/current

Get current positions.

#### GET /projection/position/{symbol}

Get position for specific symbol.

#### GET /projection/position/pnl

Get position PnL summary.

#### GET /projection/timeline

Get event timeline.

**Query Parameters:**
- `symbol` (optional): Filter by symbol
- `limit` (optional): Number of results (default: 50)

#### GET /projection/metrics

Get system metrics.

---

### Factors

#### GET /factors

Get all factors with weights.

#### GET /factors/{factor_type}

Get single factor.

#### PUT /factors/{factor_type}/weight

Update factor weight.

**Request Body:**
```json
{
  "weight": 0.25
}
```

---

### Alpha (Research)

#### GET /alpha/proposals

Get all proposals.

#### POST /alpha/proposals

Create new proposal.

**Request Body:**
```json
{
  "name": "My Proposal",
  "description": "Description",
  "type": "factor",
  "created_by": "user",
  "parameters": {}
}
```

#### PUT /alpha/proposals/{proposal_id}

Update proposal.

#### GET /alpha/snapshots

Get all snapshots.

#### POST /alpha/snapshots

Create new snapshot.

**Request Body:**
```json
{
  "name": "Snapshot Name",
  "type": "factor_weights",
  "description": "Description",
  "data": {}
}
```

#### GET /alpha/factor-lineage

Get factor change history.

---

### Prices

#### GET /price-comparison/{symbol}

Get price comparison for symbol.

**Query Parameters:**
- `symbol`: Trading pair (e.g., BTCUSDT)

#### GET /price-sources

Get price source status.

---

### WebSocket

#### WS /ws

WebSocket endpoint for real-time updates.

**Subscribe to channels:**
```json
{
  "type": "subscribe",
  "channels": ["channel:dashboard", "channel:decision", "channel:risk", "channel:position", "channel:timeline"]
}
```

**Available channels:**
- `channel:dashboard` - Dashboard updates
- `channel:decision` - Decision updates
- `channel:risk` - Risk updates
- `channel:position` - Position updates
- `channel:timeline` - Event timeline updates
- `channel:signal` - Signal updates
- `channel:order` - Order updates

---

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "detail": "Error message"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad Request
- `404` - Not Found
- `500` - Internal Server Error
