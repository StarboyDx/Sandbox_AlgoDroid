# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 引入各个模块的路由器
from routers.chat import router as chat_router
from routers.admin import router as admin_router
from routers.system import router as system_router

print("正在初始化 AIGC 游戏微服务网关...")

app = FastAPI(title = "AIGC 智能体引擎网关", version = "1.0.1")

# 跨域问题解决
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # 允许 Vue 前端访问
    allow_credentials=True,
    allow_methods=["*"], # 允许所有请求方法 (GET, POST 等)
    allow_headers=["*"], # 允许所有请求头
)

# 将路由模块化挂载到主进程
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(system_router)

if __name__ == "__main__":
    print("🚀 FastAPI 启动成功！正在监听端口 8000...")
    uvicorn.run("main:app", host = "0.0.0.0", port = 8000, reload=True)
    #http://localhost:8000/docs