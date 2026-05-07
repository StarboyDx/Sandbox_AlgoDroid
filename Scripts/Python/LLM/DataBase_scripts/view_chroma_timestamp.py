import os
import sys
import time
from datetime import datetime
# tip：记一下这个写法，其实这里直接相对路径找到chromadb实例就好了，不需要搞什么单例，脚本运行完就结束了
#      ps 但是这样好处是不用进入到这个装脚本的文件夹
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import db_manager 

# 脚本运行后输入剧本名字，就能看到这个剧本库里最新的10条设定了
def list_recent_lore(world_name: str, limit: int = 10):
    collection_name = f"kb_{world_name.lower()}"
    try:
        col = db_manager.client.get_collection(name=collection_name)
    except Exception:
        print(f"❌ 找不到世界: {world_name} 的知识库。")
        return

    # 使用 get() 而不是 query()，拉取所有数据（包含文档和元数据）
    # 如果数据量巨大，实际业务中可以用 offset 和 limit 做分页
    results = col.get(
        include=["metadatas", "documents"]
    )

    if not results["ids"]:
        print("📭 该剧本库目前为空。")
        return

    # 将拉取的数据组装成字典列表，方便在 Python 里排序
    records = []
    for i in range(len(results["ids"])):
        records.append({
            "id": results["ids"][i],
            "doc": results["documents"][i],
            "metadata": results["metadatas"][i]
        })

    # 按照 metadata 里的 timestamp 倒序排列（最新生成的在最上面）
    # 整数时间戳排序快
    records.sort(key=lambda x: x["metadata"].get("timestamp", 0), reverse=True)

    print(f"\n================= 【{world_name}】 最新 {limit} 条剧本设定 =================")
    for idx, rec in enumerate(records[:limit]):
        meta = rec["metadata"]
        ts = meta.get("timestamp", 0)
        # 将时间戳翻译成人类可读的时间
        human_time = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"\n[{idx+1}] 时间: {human_time} {ts}| 密级: Level {meta.get('level', '未知')}")
        print(f"    来源文件: {meta.get('source', '未知')}")
        print(f"    内部 ID: {rec['id']}")
        # 只打印前 50 个字预览
        preview = rec["doc"].replace('\n', ' ')[:50] + ("..." if len(rec["doc"]) > 50 else "")
        print(f"    内容预览: {preview}")
    print("\n=======================================================================")

if __name__ == "__main__":
    world = input("请输入要查看的剧本知识库 (如 Valoria): ")
    list_recent_lore(world)