import chromadb
from chromadb.utils import embedding_functions

DB_PATH = "../chroma_data" 
EMB_FN = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-small-zh-v1.5")

# 这个脚本用来清洗 ChromaDB 中某个世界观库里特定时间戳的脏数据，适用于测试过程中反复修改剧本导致的垃圾数据积累
# 配合view_chroma_timestamps.py脚本先查到对应的时间戳，再用这个脚本清洗掉
def delete_by_timestamp(world_name, target_timestamp):
    client = chromadb.PersistentClient(path=DB_PATH)
    col_name = f"kb_{world_name.lower()}"
    try:
        col = client.get_collection(name=col_name, embedding_function=EMB_FN)
        # 验证删除前后数量
        before_count = col.count()
        # where 语法匹配时间戳
        col.delete(where={"timestamp": int(target_timestamp)})
        
        after_count = col.count()
        deleted_count = before_count - after_count
        
        if deleted_count > 0:
            print(f"✅ 成功从向量库中清除了 {deleted_count} 个分块数据！(时间戳: {target_timestamp})")
            print("💡 tip：别忘了去 RawDocuments 文件夹把对应的 TXT 文件手动删掉。")
        else:
            print(f"⚠️ 库是找到了，但没有匹配到时间戳为 {target_timestamp} 的数据！(请确认你的 view 脚本查出的时间戳完全一致)")
            
    except Exception as e:
        print(f"❌ 操作失败，可能找不到对应的世界库或路径错误：{e}")

if __name__ == "__main__":
    w = input("请输入世界名 (如 Valoria): ")
    ts = input("请输入要删除的时间戳 (如 1714000000): ")
    delete_by_timestamp(w, ts)