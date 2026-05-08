import json
import os
from typing import TypedDict
from langgraph.graph import StateGraph, END
# from openai import OpenAI
from openai import AsyncOpenAI
from dotenv import load_dotenv

# tip：独立加载环境变量，注意这里和 npc_engine.py 中一样，但是要解耦
load_dotenv()

class PersonaState(TypedDict):
    world_name: str
    user_prompt: str
    retrieved_lore: str
    max_world_level: int     # 动态调整的权限等级上限，控制生成内容的尺度
    generated_json: dict
    validation_feedback: str # 审核agent的反馈
    retry_count: int         # 循环计数器防止死循环
    save_status: str

class AdminAgentWorkflow:
    def __init__(self, db_client, emb_fn):
        # self.llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
        self.llm = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
        self.model = "qwen-plus" 
        
        self.db_client = db_client
        self.emb_fn = emb_fn
        self.graph = self._build_graph()

    # ================================================
    # 将本地文件操作封装为独立工具，供 LangGraph 节点调用
    # ================================================
    def _tool_save_json_to_local(self, npc_data: dict, world_name: str) -> str:
        """
        [MCP 思想] 这是一个标准化的资源操作工具，大模型通过调用它来保存数据，而不是直接在逻辑里写文件，也确保了数据的一致性和安全性。
        """
        try:
            npc_name = npc_data.get("name", "unknown_npc").lower()
            file_path = f"./NPCSettings/{world_name}/{npc_name}.json"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(npc_data, f, ensure_ascii=False, indent=4)
            return f"✅ 成功写入文件: {file_path}"
        except Exception as e:
            return f"❌ 写入失败: {str(e)}"

    # ============================================================
    # LangGraph 工作流的各个节点实现，FastAPI 是异步的，我们也换成异步
    # ============================================================
    async def node_retrieve_lore(self, state: PersonaState):
        """node1：检索世界观，并动态获取最大 Level"""
        try:
            col = self.db_client.get_collection(name=f"kb_{state['world_name'].lower()}", embedding_function=self.emb_fn)
            # 查文本
            # res = col.query(query_texts=[state["user_prompt"]], n_results=2) # 这里没防止噪声 fixed
            # docs = res["documents"][0] if res["documents"] else ["该世界暂无相关背景。"]
            res = col.query(query_texts=[state["user_prompt"]], n_results=3)
            valid_docs = []
            if res["documents"] and res["documents"][0]:
                for doc, dist in zip(res["documents"][0], res["distances"][0]):
                    # tip：BGE 模型的 L2 距离，一般 > 1.2 就是完全不相关的废话
                    if dist < 1.2: 
                        valid_docs.append(doc)
            lore_text = "\n".join(valid_docs) if valid_docs else "该世界暂无相关背景。"
            
            # 查metadata：动态获取当前世界设定的最高等级，tip：其实这里直接查文本文件名就行
            all_data = col.get(include=["metadatas"])
            max_lvl = 1
            if all_data and all_data["metadatas"]:
                levels = [m.get("level", 1) for m in all_data["metadatas"] if m]
                if levels:
                    max_lvl = max(levels)
                    
            return {
                "retrieved_lore": lore_text,
                "max_world_level": max_lvl, 
                "retry_count": 0, 
                "validation_feedback": ""
            }
        except Exception:
            return {"retrieved_lore": "世界观未建立。", "max_world_level": 10, "retry_count": 0, "validation_feedback": ""}

    async def node_generate_persona(self, state: PersonaState):
        """node2：文案生成节点，严格的 Prompt 设计 + 重试机制"""
        count = state.get("retry_count", 0)
        feedback = state.get("validation_feedback", "")
        max_lvl = state.get("max_world_level", 10)
        
        correction_prompt = f"\n【主策退回重写要求】：{feedback}" if feedback else ""
        
        prompt = f"""
        你是一个游戏文案策划。请生成 NPC 设定 JSON。
        【世界观参考】：{state['retrieved_lore']}
        【策划需求】：{state['user_prompt']}{correction_prompt}
        
        必须返回合法 JSON，严格遵守以下规范：
        1. "name": 必须是纯英文标识（如 luna）
        2. "level": 整数。在 1 到 {max_lvl} 之间分配。（当前世界最高等级为 {max_lvl}）
        3. "persona": 详细背景描述。必须融入世界观，且【必须使用中文编写】。
        4. "tags": 字符串数组。包含2-4个简短的【中文】词汇（绝不能写长句！）。
        
        注意：除了 name 字段和 JSON 的键名外，所有的内容值必须使用中文！
        """
        try:
            res = await self.llm.chat.completions.create(
                model=self.model, 
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" } 
            )
            json_data = json.loads(res.choices[0].message.content)
            return {"generated_json": json_data, "retry_count": count + 1}
        except Exception:
            return {"generated_json": {}, "retry_count": count + 1}

    async def node_validator(self, state: PersonaState):
        """node3：逻辑审核与防幻觉"""
        persona_text = state.get("generated_json", {}).get("persona", "")
        if not persona_text:
            return {"validation_feedback": "JSON 解析失败或内容为空"}

        prompt = f"""
        请审核以下 NPC 设定是否吃书或严重违背世界观。
        世界观参考：{state['retrieved_lore']}
        NPC 设定：{persona_text}
        合理请仅输出 "PASS"；违规请指出具体错误并要求重写。
        """
        try:
            res = await self.llm.chat.completions.create(
                model=self.model, 
                messages=[{"role": "user", "content": prompt}]
            )
            feedback = res.choices[0].message.content.strip()
            
            if "PASS" in feedback.upper():
                return {"validation_feedback": "PASS"}
            else:
                print(f"\n⚠️ [LangGraph 拦截] {feedback}\n")
                return {"validation_feedback": feedback}
        except Exception:
            return {"validation_feedback": "PASS"}

    async def node_save_asset(self, state: PersonaState):
        '''node4：资源保存，调用 MCP 工具'''
        status = self._tool_save_json_to_local(state["generated_json"], state["world_name"])
        return {"save_status": status}

    def _build_graph(self):
        workflow = StateGraph(PersonaState)
        
        workflow.add_node("RetrieveLore", self.node_retrieve_lore)
        workflow.add_node("GenerateJSON", self.node_generate_persona)
        workflow.add_node("Validator", self.node_validator)
        workflow.add_node("SaveAsset", self.node_save_asset)

        workflow.set_entry_point("RetrieveLore")
        workflow.add_edge("RetrieveLore", "GenerateJSON")
        workflow.add_edge("GenerateJSON", "Validator")

        # 条件边控制循环逻辑：如果 Validator 反馈 "PASS" 则进入 SaveAsset，否则根据 retry_count 决定是重写还是放弃
        def should_save_or_rewrite(state: PersonaState):
            if state["validation_feedback"] == "PASS":
                return "save"
            elif state["retry_count"] >= 3: 
                return "abort"
            else:
                return "rewrite"

        workflow.add_conditional_edges(
            "Validator",
            should_save_or_rewrite,
            {
                "save": "SaveAsset",       
                "rewrite": "GenerateJSON", 
                "abort": END               
            }
        )
        
        workflow.add_edge("SaveAsset", END)
        return workflow.compile() # tip: 比较像tensorflow的静态图编译

    async def run_workflow(self, world_name: str, user_prompt: str):
        initial_state = {
            "world_name": world_name,
            "user_prompt": user_prompt,
            "retrieved_lore": "",
            "max_world_level": 1,
            "generated_json": {},
            "validation_feedback": "",
            "retry_count": 0,
            "save_status": ""
        }
        return await self.graph.ainvoke(initial_state)
        # return self.graph.invoke(initial_state)
    