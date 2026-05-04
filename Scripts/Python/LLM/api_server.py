from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from npc_engine import NPCAgentEngine 
from typing import Optional # 预留：未来可能添加附件处理（如图片、文件等）

print("正在初始化 AIGC 游戏引擎网关...")
agent_engine = NPCAgentEngine()
app = FastAPI(title = "AIGC 智能体引擎网关", version = "1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # 允许 Vue 前端访问
    allow_credentials=True,
    allow_methods=["*"], # 允许所有请求方法 (GET, POST 等)
    allow_headers=["*"], # 允许所有请求头
)

class ChatRequest(BaseModel):
    world_name: str = Field(..., description = "剧本名 (如 Valoria)")
    npc_name: str = Field(..., description = "NPC 名字 (如 gareth)")
    npc_level: int = Field(..., description = "权限等级")
    player_id: str = Field(..., description = "玩家 ID")
    player_message: str = Field(..., description = "玩家输入")
    attachment_id: Optional[str] = Field(default=None, description="预留：处理后的视觉/文件特征ID")

class ChatResponse(BaseModel):
    dialogue_text: str = Field(..., description = "纯文本回复，用于 UE5 UI 弹窗")
    action_type: str = Field(default = "idle", description = "动作指令映射，供 UE5 蓝图播动画")
    
    # TODO [UE5 渲染控制 / PCG]
    # level_data: dict = Field(default = None, description = "当触发自动建关卡时，传送具体的 Actor 坐标 JSON")

@app.post("/api/v1/chat", response_model = ChatResponse)
async def chat_with_npc(request: ChatRequest):
    """正常一次返回接口"""
    generator = agent_engine.chat_stream(
        request.world_name, request.npc_name, request.npc_level, request.player_id, request.player_message
    )
    full_text = "".join([chunk for chunk in generator])
    return ChatResponse(dialogue_text = full_text, action_type = "anim_talk")

# TODO [实时流式输出 Streaming 的 UE 端解析]
# 目前考虑到 UE5 原生 HTTP 模块解析 Stream 比较复杂，前期优先使用上面的 /chat 接口。
# 后续若要支持“打字机”流式效果，UE 端需要引入 VaRest 插件或自定义 C++ 线程来监听下面的 SSE 接口。
@app.post("/api/v1/chat_stream")
async def chat_with_npc_stream(request: ChatRequest):
    """流式接口 (SSE 格式)"""
    def event_generator():
        token_stream = agent_engine.chat_stream(
            world_name = request.world_name, npc_name = request.npc_name, 
            npc_level = request.npc_level, player_id = request.player_id, 
            player_input = request.player_message
        )
        for token in token_stream:
            yield f"data: {token}\n\n"
            
    return StreamingResponse(event_generator(), media_type = "text/event-stream")

if __name__ == "__main__":
    print("🚀 FastAPI 启动成功！正在监听端口 8000...")
    uvicorn.run(app, host = "0.0.0.0", port = 8000)
    #http://localhost:8000/docs