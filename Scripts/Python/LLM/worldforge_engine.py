import time
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.database import db_manager
from media_etl import MediaETLFactory
from langchain_community.chat_message_histories import RedisChatMessageHistory

# 用字典存暂时只做一次会话记录，后续可以改成 Redis 或其他存储，支持跨进程和持久化，前端功能也要匹配
# 但是我们其实这里目的是ai对话+创作，也并不需要长期记忆，触发剧本更新也是用户主动保存，这些聊天本身没有保存的必要
# 所以暂时不做升级，这里session_id表示一次会话的标志，而且每次重启就清空了
def get_session_history(session_id: str):
    """
    使用 Redis 替代内存字典，支持多进程状态共享和持久化。
    设置 3600 秒（1小时）过期时间，自动充当 LRU 垃圾回收。
    """
    redis_url = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/0"
    
    return RedisChatMessageHistory(
        session_id=session_id,
        url=redis_url,
        key_prefix="worldforge:history:",
        ttl=3600  # 1小时自动清理内存
    )

class WorldForgeEngine:
    def __init__(self):
        self.local_vl = ChatOpenAI(base_url="http://localhost:11434/v1", api_key="ollama", model="llava", max_retries=1)
        self.cloud_vl = ChatOpenAI(model="qwen-vl-plus", max_retries=2)
        self.vision_chain = self.local_vl.with_fallbacks([self.cloud_vl])
        self.text_chain = ChatOpenAI(model="qwen-plus")
        # tip: RunableWithMessageHistory 在每次调用时自动将消息记录到历史中，方便后续上下文管理和检索，
        #      但是目前只是单纯的记录，并没有做记忆压缩或长期存储，后续可以根据需求升级
        self.chat_vision = RunnableWithMessageHistory(self.vision_chain, get_session_history)
        self.chat_text = RunnableWithMessageHistory(self.text_chain, get_session_history)
        # 和data_pipeline里参数一致 tip：但这里是给前端交互用的，后续可以根据实际情况调整
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "，", " "],
            chunk_size=300,
            chunk_overlap=50,
            length_function=len
        )
        self.media_factory = MediaETLFactory()

    async def chat(self, session_id: str, world_name: str, prompt: str, use_rag: bool = False, file_bytes: bytes = None, file_name: str = None, mime_type: str = None) -> dict:
        system_context = f"【系统环境参数：当前操作空间为 '{world_name}'】\n"
        
        # 动态 RAG 开关拦截
        rag_context = ""
        if use_rag and world_name:
            try:
                # 只有打开开关，才去 ChromaDB 查当前世界的设定
                col = db_manager.client.get_or_create_collection(
                    name=f"kb_{world_name.lower()}", embedding_function=db_manager.emb_fn
                )
                results = col.query(query_texts=[prompt], n_results=3) 
                valid_docs = []
                if results and results['documents'] and results['documents'][0]:
                    for doc, dist in zip(results['documents'][0], results['distances'][0]):
                        if dist < 1.2:
                            valid_docs.append(doc)
                
                if valid_docs:
                    rag_context = "【以下是知识库中检索到的相关世界观设定，请务必参考且不要冲突】：\n" + "\n\n".join(valid_docs)
                else:
                    rag_context = "【系统提示：当前指令未命中特定知识库记录。请基于世界观常识自由发挥。】"
                    
            except Exception as e:
                print(f"RAG 检索异常: {e}")

        # === 经过 ETL 流水线提取文件信息 ===
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
        if not re.match(r"^[a-zA-Z0-9_\u4e00-\u9fa5]+$", world_name):
            # 抛出 ValueError，外层的 FastAPI 路由 try-except 会自动捕获并返回给前端 500/400 错误
            raise ValueError("创建失败：剧本名称包含非法字符！只能使用中英文、数字或下划线（不能包含空格）。")
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
        
        # 执行切块
        chunks = self.text_splitter.split_text(content)
        documents = []
        metadatas = []
        ids = []
        
        for i, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append({
                "level": level, 
                "source": file_name, 
                "timestamp": current_timestamp
            })
            ids.append(f"{file_name}_chunk_{i}")
            
        col.add(documents=documents, metadatas=metadatas, ids=ids)
        return {"status": "success", "message": f"剧本热更新完成！生效文件: {file_name}，共 {len(chunks)} 个数据块"}