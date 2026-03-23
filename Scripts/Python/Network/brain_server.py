import socket
import json

HOST = '0.0.0.0'
PORT = 9999

def algo_sliding_window(payload):
    """处理滑动窗口逻辑"""
    data_array = payload.get("radar", [])
    max_len, current_len, best_start, current_start = 0, 0, -1, -1

    for i, val in enumerate(data_array):
        if val == 1:
            if current_len == 0: current_start = i
            current_len += 1
            if current_len > max_len:
                max_len = current_len
                best_start = current_start
        else:
            current_len = 0
            
    return {"status": "success", "best_start": best_start, "max_length": max_len}

def algo_two_sum(payload):
    """预留：处理两数之和（哈希表）"""
    nums = payload.get("nums", [])
    target = payload.get("target", 0)
    hash_map = {}
    for i, num in enumerate(nums):
        if target - num in hash_map:
            return {"status": "success", "indices": [hash_map[target - num], i]}
        hash_map[num] = i
    return {"status": "failed", "reason": "No solution found"}

# 命令路由分发
# 在这注册过的指令，服务器就能自动分发处理
ALGORITHM_ROUTER = {
    "sliding_window": algo_sliding_window,
    "two_sum": algo_two_sum,
    # 未来可以继续添加: "dfs_maze": algo_dfs_maze 等
}

# 网络模块
def process_request(raw_str):
    try:
        request = json.loads(raw_str)
        action = request.get("action")
        payload = request.get("payload", {})

        # 核心分发逻辑
        if action in ALGORITHM_ROUTER:
            print(f"[Brain] Executing action: {action}")
            handler_func = ALGORITHM_ROUTER[action]
            result = handler_func(payload)
            return json.dumps(result)
        else:
            error_msg = {"Status": "error", "reason": f"Unknown action: {action}"}
            return json.dumps(error_msg)
    
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "reason": "Invalid JSON format"})
    except Exception as e:
        return json.dumps({"Status": "error", "reason": str(e)})
    
def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # 允许端口复用，防止重启 server 时报错 "Address already in use"
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"[*] AlgoDroid Universal Brain is listening on {HOST}:{PORT}...")

        while True:
            conn, addr = s.accept()
            with conn:
                print(f"[*] Connected by UE sensor at {addr}")
                while True:
                    data = conn.recv(4096) # 稍微开大点 buffer，应对以后的大数据
                    if not data:
                        break

                    raw_str = data.decode('utf-8').strip()
                    print(f"[UE Request] {raw_str}")

                    # 交给分发器处理
                    response_str = process_request(raw_str)
                    print(f"[Brain Response] {response_str}\n")

                    # 发回UE
                    conn.sendall((response_str + "\n").encode('utf-8'))

if __name__ == "__main__":
    start_server()    