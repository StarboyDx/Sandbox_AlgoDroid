import chromadb
import redis

# 脚本用来清洗玩家的长期记忆和短期记忆，适用于玩家测试过程中数据混乱需要重置的情况
# 本地的数据库
client = chromadb.PersistentClient(path=".././chroma_data")

# 拿到管长期记忆的那个池子
memory_col = client.get_collection(name="agent_long_term_memory")

# 利用 where 过滤标签，删除特定 session_id 的数据
session_to_delete = "test_player_001_gareth"

print(f"准备清洗 {session_to_delete} 的脏数据...")
memory_col.delete(
    where={"session_id": session_to_delete}
)
print("✅ 清洗完成！")

# 连接本地 Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# 方式 A：精准删除当前玩家和 NPC 的聊天历史
key_to_delete = "history:test_player_001:gareth"
r.delete(key_to_delete)
print(f"✅ 已清空短期记忆: {key_to_delete}")

# ------------------------------------------------
# 方式 B：如果你在本地随便玩，想重头来过，推荐这个
# r.flushdb()
# print("Redis DB0 已全部清空！（包含所有人的聊天历史和好感度）")