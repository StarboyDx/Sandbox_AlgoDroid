import chromadb
from chromadb.utils import embedding_functions
import redis
import os

class DatabaseManager: # [修改原理]：名字从 VectorDBManager 改得更通用一点
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        # 初始化 ChromaDB
        self.client = chromadb.PersistentClient(path="./chroma_data")
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-small-zh-v1.5"
        )
        
        # 初始化 Redis 连接池
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_pool = redis.ConnectionPool(
            host=redis_host, 
            port=redis_port, 
            db=0, 
            decode_responses=True
        )

    def get_redis(self):
        """提供给外部获取 Redis 实例的方法"""
        return redis.Redis(connection_pool=self.redis_pool)

# 全局单例
db_manager = DatabaseManager()