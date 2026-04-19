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
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# TODO: 写个外部函数让ai来决定是否调用，实现一个简单“agent”

class NPCResponse(BaseModel):
    dialogue: str = Field(description="NPC对话内容")
    emotion: Literal['Neutral', 'Angry', 'Happy', 'Suspicious'] = Field(
        description="情绪枚举"
    )
    action: Literal['Idle', 'DrawSword', 'Laugh', 'LookAround'] = Field(
        description="动作枚举"
    )

# save，注意这里是记忆的简单实现方法，非常消耗token
MEMORY_FILE = "saved/chat_history.json"

def save_memory(messages: List[BaseMessage]):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        # 转换成可存储的格式
        json.dump([{"type": m.type, "content": m.content} for m in messages], f, 
                  ensure_ascii=False)

def load_memory() -> List[BaseMessage]:
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
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

def init_npc_brain():
    print("正在为加雷斯加载记忆与世界观...")
    
    # RAG 模块 1：加载与切分 --- 将长文本切成小块，方便大模型消化
    loader = TextLoader("lore.txt", encoding = "utf-8")
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size = 200, chunk_overlap = 20)
    texts = text_splitter.split_documents(documents)

    # RAG 模块 2：Embedding --- 把文字变成数学向量，存入本地数据库
    # embeddings = OpenAIEmbeddings(model="text-embedding-v1")
    embeddings = DashScopeEmbeddings(
        model = "text-embedding-v1",
        dashscope_api_key = os.environ.get("OPENAI_API_KEY") # 自动读取你的千问 Key
    )
    vectorstore = Chroma.from_documents(
        documents = texts,
        embedding = embeddings,
        persist_directory = "./npc_chroma_db"
    )
    # 将数据库转化为检索器，每次找k条最相关的设定
    retriever = vectorstore.as_retriever(search_kwargs = {"k": 2})

    # 模型这里使用千问，实例化
    llm = ChatOpenAI(model = "qwen-plus", temperature = 0.7, timeout = 30)
    structured_llm = llm.with_structured_output(NPCResponse)
    
    # 构造系统提示词
    system_prompt = """你叫加雷斯，性格暴躁的骑士。严格根据【背景信息】回答。
    必须根据语境选择规定的 emotion 和 action。
    【背景信息】: {context}"""

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
    # 逻辑流水线：检索文档 -> 组合上下文 -> 填入 Prompt -> 交给大模型 -> 输出字符串
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

if __name__ == "__main__":
    # 读档，测试用，累计太多消耗token很快，重构前记得定期手动删
    chat_history = load_memory()
    print(f"--- 已载入 {len(chat_history)} 条历史记忆 ---")

    try:
        brain = init_npc_brain()
    except Exception as e:
        print(f"初始化失败: {e}")
        exit()
    print("\n[系统就绪] 输入 'quit' 退出。\n")
    
    #chat_history = []

    while True:
        user_input = input("[玩家]: ")
        if user_input.lower() == 'quit':
            break

        # fixed：添加ValidationError防止大模型幻觉导致程序崩溃    
        try:    
            # 抛出问题，LangChain 会自动处理检索和上下文合并
            response = brain.invoke({"question": user_input,
                                    "chat_history": chat_history})
        except ValidationError:
            # 格式错误时的回复
            print(f"\n[系统拦截] ⚠️ AI 试图输出非法动作/情绪！已自动替换为默认动作。")
            response = NPCResponse(
                dialogue="啧，你在说什么胡话？", 
                emotion="Suspicious", 
                action="LookAround"
            )
        except Exception as e:
            print(f"\n[错误] API 响应超时或异常: {e}")
            continue
        
        # test in terminal
        print(f"\n[加雷斯]: {response.dialogue} \
              (情绪: {response.emotion}, 动作: {response.action})\n")

        # 将这一轮的对话加入记忆库，让 AI 记住上下文
        chat_history.append(HumanMessage(content = user_input))
        chat_history.append(AIMessage(content = response.dialogue))
        save_memory(chat_history)