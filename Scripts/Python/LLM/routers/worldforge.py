from fastapi import APIRouter, HTTPException, File, Form, UploadFile
from typing import Optional
from pydantic import BaseModel
from worldforge_engine import WorldForgeEngine

router = APIRouter(prefix="/api/v1/worldforge", tags=["WorldForge"])
engine = WorldForgeEngine()

class SaveLoreRequest(BaseModel):
    world_name: str
    content: str
    level: int = 1

@router.post("/chat")
async def worldforge_chat(
    session_id: str = Form(...),
    world_name: str = Form(...),
    prompt: str = Form(...),
    use_rag: str = Form("false"), # 接收前端开关状态
    file: Optional[UploadFile] = File(None)
):
    """接收前端表单，支持图文/文档混合与 RAG 动态切换"""
    try:
        # 类型转换
        is_rag_enabled = use_rag.lower() == 'true'
        
        file_bytes = None
        file_name = None
        mime_type = None
        
        if file:
            file_bytes = await file.read()
            file_name = file.filename
            mime_type = file.content_type
            
        result = await engine.chat(
            session_id=session_id,
            world_name=world_name,
            prompt=prompt,
            use_rag=is_rag_enabled, # 传入核心引擎
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/save_lore")
async def save_world_lore(req: SaveLoreRequest):
    try:
        result = engine.save_dynamic_lore(req.world_name, req.content, req.level)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))