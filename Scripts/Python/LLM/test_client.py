import requests

# Flask 服务器地址
URL = "http://127.0.0.1:5000/chat"

print("===================================")
print("🎮 UE5 模拟客户端已启动")
print("===================================\n")
print("输入 'switch' 可以切换谈话对象，输入 'quit' 退出。\n")

current_npc = "gareth"

while True:
    user_text = input(f"\n[对 {current_npc} 说]: ")
    
    if user_text.lower() == 'quit':
        break
    elif user_text.lower() == 'switch':
        new_npc = input("你想切换到哪个 NPC (例如 elara)？: ").strip()
        if new_npc:
            current_npc = new_npc
            print(f"已将视线切换至: {current_npc}")
        continue

    # 打包带身份证的 JSON 负载
    payload = {
        "npc_id": current_npc,
        "message": user_text
    }

    try:
        print("⏳ 正在通过 HTTP 等待服务器响应...")
        # 超时时间设长一点，以防触发查数据库的双段思考
        response = requests.post(URL, json=payload, timeout=40) 

        if response.status_code == 200:
            data = response.json()
            print("\n✅ [成功解析网络回包]")
            print(f"🗣️ 【台词】: {data.get('dialogue')}")
            print(f"🎭 【情绪】: {data.get('emotion')}")
            print(f"🤺 【动作】: {data.get('action')}")
            
            # 客户端事件模拟
            if data.get('call_backup') == True:
                print("🚨🚨🚨 [UE5 引擎事件]: 触发 call_backup=True！执行 SpawnActor！")
            else:
                print("🔒 [UE5 引擎事件]: 维持现状。")
                
            print("-" * 35)
        else:
            print(f"\n❌ 服务器返回错误，状态码: {response.status_code}")
            print(f"详情: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ 连接失败！请检查你的 app.py 是否已经运行？")
    except Exception as e:
        print(f"\n❌ 网络异常: {e}")