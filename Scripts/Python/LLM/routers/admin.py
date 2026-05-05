from fastapi import APIRouter
from pydantic import BaseModel
from admin_agents import AdminAgentWorkflow
from core.database import db_manager

admin_workflow = AdminAgentWorkflow(db_client=db_manager.client, emb_fn=db_manager.emb_fn)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Workspace"])

class PersonaGenRequest(BaseModel):
    world_name: str
    user_prompt: str # 需求描述

# Persona.vue 的生成接口，触发 AdminAgentWorkflow 工作流
@router.post("/generate_persona")
async def admin_generate_persona(req: PersonaGenRequest):
    """触发 LangGraph 多智能体工作流 (RAG -> 生成 -> 循环校验 -> MCP入库)"""
    final_state = await admin_workflow.run_workflow(req.world_name, req.user_prompt)
    return {
        "status": "success",
        "generated_data": final_state["generated_json"],
        "message": final_state["save_status"]
    }