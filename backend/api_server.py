"""
API Server - Main Entry Point
API 服务器主入口
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_router


# ======================================
# Initialize FastAPI
# ======================================
app = FastAPI(
    title="Quantitative Trading System API",
    description="AI-assisted quantitative trading system API",
    version="1.0.0"
)


# ======================================
# CORS Configuration
# ======================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost:3004",
        "http://127.0.0.1:3004",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================
# Mount Routes
# ======================================
app.include_router(api_router, prefix="/api/v1")


import os

# ======================================
# Start Server
# ======================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    print("=" * 80)
    print("  Quantitative Trading System API Server")
    print("=" * 80)
    print(f"  Starting on: http://0.0.0.0:{port}")
    print(f"  Swagger Docs: http://0.0.0.0:{port}/docs")
    print("=" * 80)
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
