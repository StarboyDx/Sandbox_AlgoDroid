from fastapi import APIRouter, Query
import os
import glob
import json
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["System Info"])

# 扫描已有剧本
@router.get("/worlds/list")
async def get_worlds_list():
    worlds = []
    base_dir = "./RawDocuments"
    if os.path.exists(base_dir):
        for item in os.listdir(base_dir):
            if os.path.isdir(os.path.join(base_dir, item)):
                worlds.append(item)
    # if not worlds:
    #     worlds = ["Valoria"] # 兜底值
    return {"worlds": worlds}

# 扫描已有 NPC 预设
@router.get("/sandbox/presets")
async def get_sandbox_presets(world_name: Optional[str] = Query(None)):
    npcs = []
    base_dir = "./NPCSettings"
    
    if not os.path.exists(base_dir):
        return {"npcs": []}
    
    search_pattern = f"{base_dir}/{world_name}/*.json" if world_name else f"{base_dir}/**/*.json"
    
    # tip：recursive=True 允许 ** 匹配任意层级的目录
    for file_path in glob.glob(search_pattern, recursive=True):
        npc_name = os.path.basename(file_path).replace(".json", "")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                level = data.get("level", 1)
                npcs.append({"label": f"{npc_name} (Lv:{level})", "value": npc_name, "level": level})
        except Exception:
            pass
            
    return {"npcs": npcs}