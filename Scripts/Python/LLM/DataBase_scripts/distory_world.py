import chromadb

DB_PATH = "../chroma_data"

# 这个脚本用来彻底删除某个世界观库
def nuke_vector_db(world_name):
    client = chromadb.PersistentClient(path=DB_PATH)
    col_name = f"kb_{world_name.lower()}"
    try:
        client.delete_collection(name=col_name)
        print(f"✅ 世界【{world_name}】的向量记忆已删除！")
        print("💡 tip：记得手动删除对应的物理文件夹。")
    except Exception as e:
        print(f"❌ 删除失败，可能该库本来就不存在。")

if __name__ == "__main__":
    w = input("请输入要删除的世界名: ")
    nuke_vector_db(w)