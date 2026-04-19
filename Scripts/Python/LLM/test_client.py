import requests

# Flask 服务器地址
URL = "http://127.0.0.1:5000/chat"

print("===================================")
print("🎮 UE5 模拟客户端已启动")
print("📡 正在尝试连接 AI 服务器...")
print("===================================\n")

while True:
    user_text = input("[UE5 玩家输入]: ")
    if user_text.lower() == 'quit':
        break

    # 模拟UE5工具打包发送的JSON
    payload = {
        "message": user_text
    }

    try:
        # 模拟 UE5 发送 POST 请求
        print("⏳ 等待加雷斯响应中...")
        response = requests.post(URL, json=payload, timeout=30)

        # 状态码 200 代表服务器成功处理了请求
        if response.status_code == 200:
            data = response.json()
            print("\n✅[收到 AI 解析指令包]")
            print(f"【NPC台词】: {data.get('dialogue')}")
            print(f"【UE5情绪】: {data.get('emotion')}")
            print(f"【UE5动作】: {data.get('action')}")
            print("-" * 35 + "\n")
        else:
            print(f"\n❌服务器返回错误码: {response.status_code}")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("\n❌连接失败！请检查你的 app.py (服务端) 是否处于运行状态？")
    except requests.exceptions.Timeout:
        print("\n❌请求超时！AI 思考时间超过了 30 秒。")
    except Exception as e:
        print(f"\n❌发生未知异常: {e}")