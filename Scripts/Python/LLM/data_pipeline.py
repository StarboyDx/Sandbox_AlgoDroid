import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

print("checking...")

def build_world_knowledge_base(world_name: str):
    """
    通用剧本知识库构建引擎
    :param world_name: 剧本/世界的名称 (必须与 RawDocuments 下的文件夹名一致)
    """

    print(f"\n🚀 开始构建/更新 [{world_name}] 的世界观知识库...")

    raw_docs_dir = f"./RawDocuments/{world_name}"
    collection_name = f"kb_{world_name.lower()}" # 数据库集合命名规范

    if not os.path.exists(raw_docs_dir):
        print(f"❌ 错误：找不到剧本文件夹 {raw_docs_dir}，请检查路径！")
        return

    # 配置分块策略
    text_splitter = RecursiveCharacterTextSplitter(
        separators = ["\n\n", "\n", "。", "！", "？", "，", " "], # 优先按段落切，其次按句子切
        chunk_size = 300,
        chunk_overlap = 50,
        length_function = len,
    )

    # 初始化数据库
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name = "BAAI/bge-small-zh-v1.5")
    db_client = chromadb.PersistentClient(path = "./chroma_data")
    # 每次清洗数据前，清空旧数据，保证数据最新
    try:
        db_client.delete_collection(collection_name)
        print(f"🧹 已清空旧版本 [{world_name}] 数据，准备写入新版...")
    except:
        pass
    collection = db_client.create_collection(name = collection_name, embedding_function = emb_fn)

    # 读取并处理文档
    all_chunks = []
    all_metadatas = []
    all_ids = []

    # 循环读取每个层级
    for filename in os.listdir(raw_docs_dir):
        if not filename.endswith(".txt"):
            continue
            
        filepath = os.path.join(raw_docs_dir, filename)
        print(f"正在解析文档: {filename}")
        
        # 从文件名中提取权限等级 (例如从 Level_1_Public.txt 提取出 1)
        # 利用目录结构或文件名来做 Metadata 自动化注入
        level = 1
        if "Level_" in filename:
            try:
                level = int(filename.split("Level_")[1].split("_")[0])
            except Exception as e:
                print(f"❌ 错误：无法解析文件 {filename} 的权限等级，使用默认值 1。错误信息: {e}")

        # 使用 LangChain TextLoader 读取 TXT
        loader = TextLoader(filepath, encoding = 'utf-8')
        docs = loader.load()
        
        # 智能切分文档，保持上下文连贯
        chunks = text_splitter.split_documents(docs)
        
        print(f"  -> 该文档被切分为 {len(chunks)} 块 (带有 {50} 字 Overlap)")
        
        # 组装入库格式
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk.page_content)
            all_metadatas.append({
                "level": level,
                "source": filename # 记录来源，方便溯源
            })
            all_ids.append(f"{filename}_chunk_{i}")

    if all_chunks:
        # 批量向量化并存入数据库
        print(f"\n总计生成 {len(all_chunks)} 个数据块。正在向量化入库...")
        collection.add(
            documents=all_chunks,
            metadatas=all_metadatas,
            ids=all_ids
        )

        print(f"✅ [{world_name}] 知识库构建完成！")
    else:
        print(f"⚠️ [{world_name}] 文件夹为空，没有数据入库。")

#test
if __name__ == "__main__":
    build_world_knowledge_base("Valoria")