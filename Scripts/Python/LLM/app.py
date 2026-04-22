from flask import Flask, request, jsonify
from langchain_core.messages import HumanMessage, AIMessage
# from pydantic import ValidationError
from npc_brain import init_npc_brain, load_memory, save_memory, agent_process

app = Flask(__name__)
# 缓存npc brain
brain_pool = {}

print("--- 正在启动 AI 神经网关 ---")

# 冷启动防止卡顿
try:
    print("⏳ 正在预热默认npc【gareth】...")
    brain_pool['gareth'] = init_npc_brain('gareth')
    print("✅ 预热完成，网关就绪！\n")
except Exception as e:
    print(f"⚠️ 预热加雷斯失败（请检查设定文件），但不影响网关启动。错误: {e}")

# Flask  接口地址： POST http://127.0.0.1:5000/chat
@app.route('/chat', methods=['POST'])
def chat_with_npc():
    # 获取UE5发来的JSON数据
    data = request.json
    if not data or 'message' not in data:
        return jsonify({"error": "数据包格式错误"}), 400
    
    npc_id = data.get('npc_id', 'gareth') # 默认路由给gareth
    user_input = data['message']
    print(f"\n[收到 UE5 请求] npc: {npc_id} | 玩家：{user_input}")
    # Lazy Loading
    if npc_id not in brain_pool:
        try:
            print(f"正在将【{npc_id}】装载进内存...")
            brain_pool[npc_id] = init_npc_brain(npc_id)
        except Exception as e:
            print(f"❌ 挂载失败: {e}")
            return jsonify({"error": f"无法初始化 NPC【{npc_id}】"}), 500
    # 提取当前NPC的所有记忆
    full_history = load_memory(npc_id)

    try:
        # 刚封装的agent推理管线
        result = agent_process(npc_id, user_input, full_history, brain_pool[npc_id])
        
        # 更新对应npc记忆
        full_history.append(HumanMessage(content=user_input))
        full_history.append(AIMessage(content=result["dialogue"]))
        save_memory(npc_id, full_history)

        print(f"[返回给 UE5] 动作: {result['action']} | 摇人: {result['call_backup']}")
        return jsonify(result)
    
    except Exception as e: 
        print(f"[错误] 服务器异常: {e}")
        return jsonify({"error": "AI 服务器发生内部故障"}), 500

if __name__ == '__main__':
    # 测试端口host='0.0.0.0' 允许局域网内其他设备访问
    app.run(host='0.0.0.0', port=5000)