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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================
# Mount Routes
# ======================================
app.include_router(api_router, prefix="/api/v1")


# ======================================
# Start Server
# ======================================
if __name__ == "__main__":
    print("=" * 80)
    print("  Quantitative Trading System API Server")
    print("=" * 80)
    print(f"  Starting on: http://0.0.0.0:8001")
    print(f"  Swagger Docs: http://0.0.0.0:8001/docs")
    print("=" * 80)
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
