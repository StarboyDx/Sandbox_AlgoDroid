from flask import Flask, request, jsonify
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import ValidationError
from npc_brain import init_npc_brain, load_memory, save_memory

app = Flask(__name__)

print("--- 正在启动 AI 神经网关 ---")
try:
    brain = init_npc_brain()
    chat_history = load_memory() # TODO
    print(f"--- 记忆加载完成，当前记忆数: {len(chat_history)} ---")
except Exception as e:
    print(f"error！ 启动失败: {e}")
    exit()

# Flask  接口地址： POST http://127.0.0.1:5000/chat
@app.route('/chat', methods=['POST'])
def chat_with_npc():
    # 获取UE5发来的JSON数据
    data = request.json
    if not data or 'message' not in data:
        return jsonify({"error": "支支吾吾吐不出一个字？"}), 400
    
    user_input = data['message']
    print(f"\n[收到 UE5 请求] 玩家: {user_input}")

    # 呼叫大模型
    try:
        response = brain.invoke({
            "question": user_input,
            "chat_history": chat_history
        })
        # 将结构体拆解为普通的字典，方便Flask转换成JSON
        result = {
            "dialogue": response.dialogue,
            "emotion": response.emotion,
            "action": response.action
        }
    except ValidationError:
        print("[拦截] 格式错误，默认效果。")
        result = {
            "dialogue": "（掏了掏耳朵）风声太大，你再说一遍？",
            "emotion": "Neutral",
            "action": "Idle"
        }
    except Exception as e:
        print(f"[错误] API 异常: {e}")
        return jsonify({"error": "AI 服务器走神了"}), 500
    
    # 更新记忆 ## TODO
    chat_history.append(HumanMessage(content=user_input))
    chat_history.append(AIMessage(content=result["dialogue"]))
    save_memory(chat_history)

    print(f"[返回给 UE5] 动作: {result['action']}, 情绪: {result['emotion']}")

    # 将结果打包成标准 JSON 发回给 UE5
    return jsonify(result)

if __name__ == '__main__':
    # 测试端口host='0.0.0.0' 允许局域网内其他设备访问（比如你要用另一台电脑联调）
    app.run(host='0.0.0.0', port=5000)