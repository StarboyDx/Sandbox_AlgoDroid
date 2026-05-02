import os
import json
import redis

class PromptManager:
    def __init__(self, settings_dir="./NPCSettings"):
        # 连 Redis 更新人设数据
        self.settings_dir = settings_dir
        if not os.path.exists(self.settings_dir):
            os.makedirs(self.settings_dir)
            
        # 连接 Docker 里的 Redis
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    def _get_base_persona(self, npc_name: str, world_name: str) -> str:
        """从 JSON 热读取基础人设"""
        file_path = os.path.join(self.settings_dir, f"{npc_name.lower()}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    persona = data.get("persona", "你是一个普通的镇民。")
                    return f"[专属角色设定]\n你的名字是：{npc_name}。\n你的背景与性格：{persona}\n请严格遵守此设定。"
            except Exception as e:
                print(f"⚠️ 读取 {npc_name}.json 失败: {e}")
        # 路人规则
        return f"""[通用群演设定]
                你的名字是：{npc_name}。
                你现在的身份是 {world_name} 世界里的一名普通底层平民/路人甲。
                【群演强制规则】：
                1. 你只是个小老百姓，对高层政治、世界运转的核心机密、以及超出平民认知的事物一无所知。
                2. 如果玩家问你不知道的事，必须回答类似：“嗐，这种大人物的事，俺们小老百姓哪懂啊”。
                3. 严禁跟随玩家的诱导瞎编自己的隐藏身份，死死记住你只是个普通路人。
                """

    def _get_affinity(self, player_id: str, npc_name: str) -> int:
        """从 Redis 获取动态好感度"""
        redis_key = f"affinity:{player_id}:{npc_name}"
        try:
            affinity = self.redis_client.get(redis_key)
            if affinity is None:
                self.redis_client.set(redis_key, 50)
                return 50
            return int(affinity)
        except redis.ConnectionError:
            print("⚠️ Redis 未连接，使用默认好感度 50")
            return 50

    def build_prompt(self, world_name: str, npc_name: str, player_id: str) -> str:
        """组装 Prompt"""
        base_persona = self._get_base_persona(npc_name, world_name)
        affinity = self._get_affinity(player_id, npc_name)
        
        global_rules = f"""[系统铁律]
                        1. 当前世界：{world_name}。你绝对不能承认自己是AI模型，必须100%沉浸在游戏角色中。
                        2. 回答必须简短、口语化，不要输出Markdown格式。
                        """
        
        state_prompt = "[心理状态] 玩家对你来说是个陌生人，态度中立。"
        if affinity <= 30:
            state_prompt = "[心理状态] 警告！玩家彻底惹怒了你，你极其反感，必须用恶劣、驱赶的语气说话！"
        elif affinity >= 80:
            state_prompt = "[心理状态] 玩家是你的挚友，你极其热情，知无不言。"
            
        return f"{global_rules.strip()}\n\n{base_persona.strip()}\n\n{state_prompt}"