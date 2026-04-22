import os
import json
from dotenv import load_dotenv 
from operator import itemgetter # 传文本
from typing import Literal, List # 字面量
from pydantic import BaseModel, Field, ValidationError
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
# from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_chroma import Chroma
# from langchain.chains import ConversationalRetrievalChain
# from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
# from langchain_core.runnables import RunnablePassthrough
# from langchain_core.output_parsers import StrOutputParser # 字符串测试

load_dotenv()

MAX_HISTORY_LEN = 10 # 滑动窗口大小

# 结构化的输出，包含指令和对话
class NPCResponse(BaseModel):
    dialogue: str = Field(description = "NPC对话内容")
    emotion: Literal['Neutral', 'Angry', 'Happy', 'Suspicious'] = Field(
        description = "情绪枚举"
    )
    action: Literal['Idle', 'DrawSword', 'Laugh', 'LookAround'] = Field(
        description = "动作枚举"
    )
    # 客户端指令Test
    call_backup: bool = Field(description = "是否需要呼叫帮手。")
    # 服务端指令Test
    need_check_wanted: bool = Field(description = "是否需要查阅通缉令。")
    target_name: str = Field(description = "通缉令目标姓名，否则为空。")

# test
def get_memory_path(npc_id: str):
    os.makedirs("saved", exist_ok = True)
    return f"saved/chat_history_{npc_id}.json"  
def save_memory(npc_id: str, messages: List[BaseMessage]):
    with open(get_memory_path(npc_id), "w", encoding="utf-8") as f:
        # 转换成可存储的格式
        json.dump([{"type": m.type, "content": m.content} for m in messages], f, 
                  ensure_ascii=False)
def load_memory(npc_id: str) -> List[BaseMessage]:
    path = get_memory_path(npc_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            messages = []
            for m in data:
                if m["type"] == "human": 
                    messages.append(HumanMessage(content=m["content"]))
                else:
                    messages.append(AIMessage(content=m["content"]))
            return messages
    except:
        return []

def init_npc_brain(npc_id: str):
    # RAG 模块 1：加载与切分 --- 将长文本切成小块，方便大模型消化
    lore_path = f"NPCSettings/{npc_id}_lore.txt"
    prompt_path = f"NPCSettings/prompts/{npc_id}_prompt.txt"
    db_path = f"npc_chroma_db/npc_chroma_db_{npc_id}"
    loader = TextLoader(lore_path, encoding = "utf-8")
    texts = CharacterTextSplitter(chunk_size = 200, chunk_overlap = 20).\
        split_documents(loader.load())

    # RAG 模块 2：Embedding --- 把文字变成数学向量，存入本地数据库
    # embeddings = OpenAIEmbeddings(model="text-embedding-v1")
    embeddings = DashScopeEmbeddings(
        model = "text-embedding-v1",
        dashscope_api_key = os.environ.get("OPENAI_API_KEY") # 自动读取千问 Key
    )
    vectorstore = Chroma.from_documents(
        documents = texts,
        embedding = embeddings,
        persist_directory = db_path
    )
    # 将数据库转化为检索器，每次找k条最相关的设定
    retriever = vectorstore.as_retriever(search_kwargs = {"k": 2})

    # 模型这里使用千问，实例化
    llm = ChatOpenAI(model = "qwen-plus", temperature = 0.7, timeout = 30)
    structured_llm = llm.with_structured_output(NPCResponse)
    
    # # 构造系统提示词
    # system_prompt = """你叫加雷斯，性格暴躁的骑士。严格根据【背景信息】回答。
    # 必须根据语境选择规定的 emotion 和 action。
    # 【背景信息】: {context}"""
    with open(prompt_path, "r", encoding = 'utf-8') as f:
        system_prompt = f.read()

    # 组合prompt：系统设定+历史记忆+玩家新问题
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name = "chat_history"), # 这里用来插入记忆
        ("human", "{question}")
    ])

    # 辅助函数：把检索到的文档拼接成纯文本
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # 组装Chain LCEL
    # 逻辑流水线：检索文档 -> 组合上下文 -> 填入 Prompt -> 交给大模型 -> 结构化输出
    rag_chain = (
        {   
            # 使用 itemgetter 单独把字典里的 "question" 字符串提取出来，喂给检索器
            "context": itemgetter("question") | retriever | format_docs, # 自动执行检索并格式化
            "question": itemgetter("question"),  # 原样透传玩家问题
            "chat_history": itemgetter("chat_history") # 原样透传历史记录
        }
        | qa_prompt
        | structured_llm
        # | llm
        # | StrOutputParser() 返回str就开启这个，一般还是用结构体
    )
    return rag_chain

# test
def check_wanted_list(target_name: str) -> str:
    print(f"\n[后端静默执行] 查阅通缉令【{target_name}】...")
    if target_name.lower() in ["fff", "ccc"]:
        return f"警告：【{target_name}】是重犯！必须逮捕！"
    return f"【{target_name}】没有任何犯罪记录，是个良民。"

def agent_process(npc_id: str, user_input: str, full_history: list, brain_chain) -> dict:
    # 滑动窗口压缩一下历史对话
    active_history = full_history[-MAX_HISTORY_LEN:]
    if len(full_history) > MAX_HISTORY_LEN:
        print(f"[上下文管理] 历史已达 {len(full_history)} 条，\
              仅发送最近 {MAX_HISTORY_LEN} 条。")
        
    try:
        # 第一阶段思考
        response = brain_chain.invoke({"question": user_input, "chat_history": active_history})
        
        # 服务端工具调用 (ReAct) test
        if response.need_check_wanted and response.target_name:
            result = check_wanted_list(response.target_name)
            # 第二段思考，要把刚才的对话也加入历史片段
            temp_history = active_history + [HumanMessage(content=user_input), \
                                             AIMessage(content="(查阅卷宗...)")]
            response = brain_chain.invoke({"question": f"【系统提示】：{result}", "chat_history": temp_history})
            
        # 打包安全字典返回给 Web 服务器
        return response.model_dump()

    except ValidationError:
        print("[拦截] 模型幻觉")
        return {
            "dialogue": "（掏了掏耳朵）风声太大，你再说一遍？",
            "emotion": "Suspicious",
            "action": "Idle",
            "call_backup": False
        }
    except Exception as e:
        raise e

if __name__ == "__main__":
    test_npc_id = input("测试 ID (gareth/elara): ").strip() or "gareth"
    brain = init_npc_brain(test_npc_id)
    history = load_memory(test_npc_id)
    
    while True:
        user_input = input("\n[玩家]: ")
        if user_input.lower() == 'quit': 
            break
        res = agent_process(test_npc_id, user_input, history, brain)
        print(f"[{test_npc_id}]: {res['dialogue']} (摇人: {res['call_backup']})")
        history.append(HumanMessage(content=user_input))
        history.append(AIMessage(content=res['dialogue']))
        save_memory(test_npc_id, history)