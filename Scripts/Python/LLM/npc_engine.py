import os
import json
import redis
import chromadb
import jieba
import uuid
from rank_bm25 import BM25Okapi
from chromadb.utils import embedding_functions
from openai import OpenAI
from dotenv import load_dotenv
from prompt_manager import PromptManager

load_dotenv()

class NPCAgentEngine:
    def __init__(self):
        self.llm_client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"), base_url = os.getenv("OPENAI_BASE_URL"))
        self.llm_model = "qwen-plus" # 大模型
        
        self.slm_client = OpenAI(api_key = "ollama", base_url = "http://localhost:11434/v1")
        self.slm_model_local = "qwen2.5:1.5b" # 本地小模型
        self.slm_model_cloud = "qwen-turbo"   # 在线小模型
        
        self.redis_client = redis.Redis(host = 'localhost', port = 6379, db = 0, decode_responses = True)
        self.prompt_manager = PromptManager()
        # RAG 
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name = "BAAI/bge-small-zh-v1.5")
        self.db_client = chromadb.PersistentClient(path = "./chroma_data")

        # Reranker  
        # tip：相当于在检索到候选文档后，使用一个专门的模型来对这些文档进行更细粒度的相关性评分，从而选出最相关的那个。
        #      这在游戏场景中尤其重要，因为玩家的输入可能包含很多模糊或特定于游戏世界的术语，简单的向量检索可能无法准确捕捉这些细微差别。
        #      通过引入 Reranker，我们可以显著提升 NPC 回答的准确性和相关性，增强玩家的沉浸感。
        try:
            from sentence_transformers import CrossEncoder
            # 这里使用 BAAI 官方开源的轻量级重排模型
            self.reranker = CrossEncoder('BAAI/bge-reranker-base')
            print(" Reranker 重排模型加载成功!")
        except ImportError:
            self.reranker = None
            print("⚠️ 警告：未安装 sentence-transformers，RAG 降级为粗排模式。")

        # 初始化长期记忆库
        self.memory_col = self.db_client.get_or_create_collection(
            name="agent_long_term_memory",  # 表名，与世界观比如kb_valoria区分开
            embedding_function=self.emb_fn
        )

    # 这里专门给网页端那个记忆提炼
    def distill_memory(self, player_id: str, npc_name: str) -> dict:
        """从 Redis 读取近期对话，让大模型提炼关键信息，存入 ChromaDB"""
        history = self._get_history(player_id, npc_name)
        # 如果聊天记录太少，就不浪费 Token 去提炼了
        if len(history) < 4:
            return {"status": "skip", "msg": "对话轮数较少，暂时无需提炼。"}

        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
        
        prompt = f"""
        请分析以下玩家与NPC({npc_name})的对话，提取关于玩家的偏好、重要承诺或关键事件。
        以第三人称陈述句输出，每条结论简明扼要。如果没有重要信息，请只回复“无”。
        [对话历史]：\n{history_text}\n[提取的长期记忆]："""

        try:
            # 调用小模型进行总结
            res = self.llm_client.chat.completions.create(
                model=self.slm_model_cloud,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            distilled_facts = res.choices[0].message.content.strip()

            if "无" in distilled_facts and len(distilled_facts) < 10:
                 return {"status": "skip", "msg": "未提取到需要长期保存的信息。"}

            # 将多条事实切分，打上特定玩家和NPC的标签，存入向量库
            facts_list = [f.strip() for f in distilled_facts.split('\n') if f.strip()]
            session_id = f"{player_id}_{npc_name}" # 隔离标识
            
            for fact in facts_list:
                self.memory_col.add(
                    documents=[fact],
                    metadatas=[{"session_id": session_id}],
                    ids=[str(uuid.uuid4())]
                )
            print(f"\n [记忆提炼完成] 为 [{session_id}] 存档了 {len(facts_list)} 条记忆:\n {facts_list}\n")
            return {"status": "success", "msg": f"成功提炼并存入 {len(facts_list)} 条长期记忆！"}
        except Exception as e:
            print(f"记忆提炼失败: {str(e)}")
            return {"status": "error", "msg": f"提炼失败: {str(e)}"}

    # ===========================================================
    # Short-term Memory (STM) 设计：基于 Redis 的轻量级对话历史存储
    # ===========================================================
    def _get_history(self, player_id: str, npc_name: str) -> list:
        """从 Redis 提取最近的聊天记录"""
        key = f"history:{player_id}:{npc_name}"
        try:
            raw_history = self.redis_client.lrange(key, 0, -1)
            return [json.loads(msg) for msg in raw_history]
        except:
            return []

    def _save_history(self, player_id: str, npc_name: str, user_msg: str, assistant_msg: str):
        """保存这一轮对话，控制记忆长度防止 Token 爆炸"""
        key = f"history:{player_id}:{npc_name}"
        try:
            self.redis_client.rpush(key, json.dumps({"role": "user", "content": user_msg}, ensure_ascii=False))
            self.redis_client.rpush(key, json.dumps({"role": "assistant", "content": assistant_msg}, ensure_ascii=False))
            self.redis_client.ltrim(key, -10, -1) # 保留最近 5 轮 (10条记录)
        except:
            pass

    # ==========================================
    # 路由与工具箱
    # ==========================================
    def _route_intent(self, text: str) -> str:
        prompt = f"分析文本，输出 chat、lore、action 之一。输入: {text}"
        messages = [{"role": "user", "content": prompt}]
        try:
            res = self.slm_client.chat.completions.create(model = self.slm_model_local, messages = messages, temperature = 0.1)
            return res.choices[0].message.content.strip().lower()
        except:
            res = self.llm_client.chat.completions.create(model = self.slm_model_cloud, messages = messages, temperature = 0.1)
            return res.choices[0].message.content.strip().lower()

    def _tool_check_inventory(self, player_id: str): return {"gold": 5, "items": ["铁剑"]}

    def _tool_update_affinity(self, player_id: str, npc_name: str, value_change: int):
        redis_key = f"affinity:{player_id}:{npc_name}"
        try:
            current = int(self.redis_client.get(redis_key) or 50)
            new_val = max(0, min(100, current + value_change))
            self.redis_client.set(redis_key, new_val)
            print(f"  [状态机] {npc_name} 好感度更新为: {new_val}")
            return {"status": "success", "new_affinity": new_val}
        except Exception: 
            return {"status": "error"}

    # =============================================
    # Query 改写，尤其是代词的还原，提升模型理解准确率
    # =============================================
    def _rewrite_query(self, player_input: str, history_messages: list) -> str:
        """利用小模型和历史记录，将代词还原为完整实体"""
        if not history_messages:
            return player_input # 没有历史，直接返回
            
        # 提取最近的对话记录转换为纯文本
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history_messages[-4:]])
        
        prompt = f"""
                    请根据以下聊天历史，改写玩家的最新输入，使其成为一句不包含代词（它、那个、他等）的独立完整句子。
                    如果输入已经很完整，直接返回原话，不要多说废话。
                    [历史记录]
                    {history_text}
                    [玩家最新输入] {player_input}
                    [改写结果]："""
        
        try:
            # 本地小模型改写
            res = self.slm_client.chat.completions.create(
                model = self.slm_model_local, 
                messages = [{"role": "user", "content": prompt}],
                temperature = 0.1
            )
        except:
            # 在线模型
            res = self.llm_client.chat.completions.create(
                model = self.slm_model_cloud, 
                messages = [{"role": "user", "content": prompt}],
                temperature = 0.1
            )
        rewritten_query = res.choices[0].message.content.strip()
        print(f"  [Query改写] 原始: '{player_input}' -> 改写为: '{rewritten_query}'")
        return rewritten_query

    # ===========================================================================================
    # 基于ChromaDB，用jieba和BM25实现的混合检索工具，也就是分词+TF-IDF，适应游戏场景专有名词的召回需求。
    # ===========================================================================================
    def _tool_search_lore(self, query_text: str, npc_level: int, world_name: str):
        try:
            col = self.db_client.get_collection(name = f"kb_{world_name.lower()}", embedding_function = self.emb_fn)
            
            # Recall 双路召回：向量检索 + BM25 关键词检索
            # tips：1. 向量召回 (Dense Retrieval) ，相当于算余弦相似度，懂语义但可能专有名词不准
            vector_res = col.query(query_texts = [query_text], n_results = 5, where = {"level": {"$lte": npc_level}})
            vector_docs = vector_res["documents"][0] if vector_res["documents"] else []
            
            # tips: 2. BM25 关键词召回 (Sparse Retrieval) 公式基于词频和逆文档频率，针对专有名词，不懂语义，适合游戏背景设定
            # tips：3. 从库里拿出符合 level 的所有文本建立临时 BM25 索引 (游戏知识库通常很小，纯内存秒级完成)
            all_data = col.get(where = {"level": {"$lte": npc_level}})
            all_docs = all_data["documents"]
            
            bm25_docs = []
            if all_docs:
                # 使用 jieba 进行中文分词
                tokenized_corpus = [list(jieba.cut(doc)) for doc in all_docs]
                bm25 = BM25Okapi(tokenized_corpus)
                tokenized_query = list(jieba.cut(query_text))
                # 拿取得分最高的前 5 条
                bm25_docs = bm25.get_top_n(tokenized_query, all_docs, n = 5)
                
            # 合并双路结果并用set去重 (Deduplication)
            combined_docs = list(set(vector_docs + bm25_docs))
            
            if not combined_docs:
                return ["没有任何相关线索。"]

            # Reranker：精排，选出最相关的那个，提升准确率，尤其是当向量检索和关键词检索结果不一致时。
            if self.reranker:
                pairs = [[query_text, doc] for doc in combined_docs]
                scores = self.reranker.predict(pairs)
                scored_docs = sorted(zip(scores, combined_docs), key = lambda x: x[0], reverse = True)
                best_doc = scored_docs[0][1]
                print(f"  [混合检索+精排] 成功选出最优记忆！")
                return [best_doc]
            else:
                return [combined_docs[0]]
                
        except Exception as e: 
            return ["当前世界尚未建立记忆库。"]

    # TODO [自动化关卡生成 PCG]
    # def _tool_generate_level(self, description: str) -> dict:
    #     """
    #     接收大模型的场景描述，生成 UE5 资产的坐标矩阵。
    #     返回例如: {"actors": [{"type": "BP_Tent", "loc": [0,0,0]}]}
    #     前端 UE5 解析此 JSON 后使用 SpawnActor 动态生成关卡。
    #     """
    #     pass

    @property
    def tools_config(self):
        return [
            {"type": "function", "function": {"name": "check_inventory", "description": "查背包金币物品", "parameters": {"type": "object", "properties": {"player_id": {"type": "string"}}, "required": ["player_id"]}}},
            {"type": "function", "function": {"name": "search_lore", "description": "查世界观", "parameters": {"type": "object", "properties": {"query_text": {"type": "string"}}, "required": ["query_text"]}}},
            {"type": "function", "function": {"name": "update_affinity", "description": "玩家态度恶劣或讨好时调用，改变好感度。", "parameters": {"type": "object", "properties": {"player_id": {"type": "string"}, "npc_name": {"type": "string"}, "value_change": {"type": "integer"}}, "required": ["player_id", "npc_name", "value_change"]}}}
        ]

    # =========================================
    # 流式调度：根据意图不同，调度不同的模型和工具
    # =========================================
    def chat_stream(self, world_name: str, npc_name: str, npc_level: int, player_id: str, player_input: str):
        system_prompt = self.prompt_manager.build_prompt(world_name, npc_name, player_id)
        history_messages = self._get_history(player_id, npc_name)
        rewritten_input = self._rewrite_query(player_input, history_messages)

        # 检索此玩家的专属长期记忆，添加到系统提示里，提升个性化和上下文连续性
        session_id = f"{player_id}_{npc_name}" # tip：这里确保了每个玩家和NPC记忆隔离的
        try:
            mem_res = self.memory_col.query(
                query_texts=[rewritten_input],
                n_results=2, # 找出最相关的2条过往记忆
                where={"session_id": session_id}
            )
            mem_docs = mem_res["documents"][0] if mem_res["documents"] else []
            if mem_docs:
                ltm_context = "\n".join(mem_docs)
                print(f"\n [长期记忆召回] 触发！召回到关于该玩家的记忆:\n {ltm_context}\n")
                system_prompt += f"\n\n[长期记忆回忆] 看到玩家的话，你脑海中浮现出以下关于该玩家的记忆：\n{ltm_context}"
        except Exception:
            pass # 如果库是空的或报错，就不打扰对话流

        messages = [{"role": "system", "content": system_prompt}] + history_messages + [{"role": "user", "content": rewritten_input}]
        
        intent = self._route_intent(rewritten_input)
        full_response_text = ""

        if intent == 'chat':
            response = self.llm_client.chat.completions.create(model = self.slm_model_cloud, messages = messages, stream = True)
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    full_response_text += content
                    yield content
        else:
            response = self.llm_client.chat.completions.create(model = self.llm_model, messages = messages, tools = self.tools_config, tool_choice = "auto")
            tool_calls = response.choices[0].message.tool_calls
            
            if tool_calls:
                messages.append(response.choices[0].message)
                for call in tool_calls:
                    args = json.loads(call.function.arguments)
                    if call.function.name == "check_inventory": 
                        res = self._tool_check_inventory(player_id)
                    elif call.function.name == "search_lore": 
                        res = self._tool_search_lore(args["query_text"], npc_level, world_name)
                    elif call.function.name == "update_affinity": 
                        res = self._tool_update_affinity(player_id, npc_name, args["value_change"])
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(res, ensure_ascii=False)})
                
                final_res = self.llm_client.chat.completions.create(model = self.llm_model, messages = messages, stream = True)
                for chunk in final_res:
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response_text += content
                        yield content
            else:
                fallback_res = self.llm_client.chat.completions.create(model = self.llm_model, messages = messages, stream = True)
                for chunk in fallback_res:
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response_text += content
                        yield content
                        
        self._save_history(player_id, npc_name, player_input, full_response_text)