import time
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from core.database import db_manager
from media_etl import MediaETLFactory

session_store = {}
def get_session_history(session_id: str):
    if session_id not in session_store:
        session_store[session_id] = ChatMessageHistory()
    return session_store[session_id]

class WorldForgeEngine:
    def __init__(self):
        self.local_vl = ChatOpenAI(base_url="http://localhost:11434/v1", api_key="ollama", model="llava", max_retries=1)
        self.cloud_vl = ChatOpenAI(model="qwen-vl-plus", max_retries=2)
        self.vision_chain = self.local_vl.with_fallbacks([self.cloud_vl])
        self.text_chain = ChatOpenAI(model="qwen-plus")

        self.chat_vision = RunnableWithMessageHistory(self.vision_chain, get_session_history)
        self.chat_text = RunnableWithMessageHistory(self.text_chain, get_session_history)
        
        self.media_factory = MediaETLFactory()

    async def chat(self, session_id: str, world_name: str, prompt: str, use_rag: bool = False, file_bytes: bytes = None, file_name: str = None, mime_type: str = None) -> dict:
        
        system_context = f"【当前世界观剧本：{world_name}】\n"
        
        # 动态 RAG 开关拦截
        rag_context = ""
        if use_rag and world_name:
            try:
                # 只有打开开关，才去 ChromaDB 查当前世界的设定
                col = db_manager.client.get_or_create_collection(
                    name=f"kb_{world_name.lower()}", embedding_function=db_manager.emb_fn
                )
                results = col.query(query_texts=[prompt], n_results=3) # Top-K 召回
                if results and results['documents'] and results['documents'][0]:
                    rag_context = "【以下是知识库中已有的世界观设定，请务必遵循且不要冲突】：\n" + "\n".join(results['documents'][0])
            except Exception as e:
                print(f"RAG 检索异常: {e}")

        # === 经过 ETL 流水线榨干文件信息 ===
        media_text = ""
        image_list = []
        if file_bytes:
            media_text, image_list = await self.media_factory.process(file_bytes, file_name, mime_type)

        # === 智能组装 LangChain 消息 (融合了 RAG 内容) ===
        final_prompt = f"{system_context}\n{rag_context}\n{media_text}\n【用户指令】：{prompt}"
        content_payload = [{"type": "text", "text": final_prompt}]
        
        # 如果流水线提取出了画面（图片本身或视频截图），就塞进 payload
        for img_b64 in image_list:
            content_payload.append({"type": "image_url", "image_url": {"url": img_b64}})

        msg = HumanMessage(content=content_payload)

        # === 智能路由引擎 ===
        if image_list: # 有图/视频，走多模态视觉大模型
            res = await self.chat_vision.ainvoke([msg], config={"configurable": {"session_id": session_id}})
            return {"reply": res.content, "engine": "Vision-Multimodal-Engine"}
        else:          # 纯文字/文档/纯语音，走纯文本大模型（速度更快，推理更深）
            res = await self.chat_text.ainvoke([msg], config={"configurable": {"session_id": session_id}})
            return {"reply": res.content, "engine": "Text-Logic-Engine"}

    def save_dynamic_lore(self, world_name: str, content: str, level: int = 1):
        """将生成的设定写入 TXT 并热更新至 ChromaDB"""
        current_timestamp = int(time.time())
        # 冷启动时兼容的命名策略
        file_name = f"Level_{level}_Dynamic_Lore_{current_timestamp}.txt"
        base_dir = f"./RawDocuments/{world_name}"
        os.makedirs(base_dir, exist_ok=True)
        # 保存 TXT
        with open(os.path.join(base_dir, file_name), "w", encoding="utf-8") as f:
            f.write(content)
            
        # 落盘向量库
        col = db_manager.client.get_or_create_collection(
            name=f"kb_{world_name.lower()}", embedding_function=db_manager.emb_fn
        )
        col.add(
            documents=[content],
            metadatas=[{"source": file_name, "level": level, "timestamp": current_timestamp, "type": "dynamic"}],
            ids=[f"{file_name}_chunk_0"]
        )
        return {"status": "success", "message": f"剧本热更新完成！生效文件: {file_name}"}