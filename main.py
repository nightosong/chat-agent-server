import argparse
from datetime import datetime

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.loggers import logger

load_dotenv()

app = FastAPI()

# 配置CORS中间件
origins = [
    "http://localhost",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="运行FastAPI应用")
    parser.add_argument("--host", default="0.0.0.0", help="监听的主机地址")
    parser.add_argument("--port", type=int, default=8000, help="监听的端口号")
    args = parser.parse_args()

    logger.info(f"应用将在 {args.host}:{args.port} 启动")
    uvicorn.run(app, host=args.host, port=args.port)
