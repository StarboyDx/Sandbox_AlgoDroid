<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { Picture, Position, Coin } from '@element-plus/icons-vue'
import axios from 'axios' // 计划用来处理图片
import { ElMessage } from 'element-plus' // 引入 Element 的消息弹窗

// ====== 顶部配置状态======
// 提供给网页修改，发给后端匹配对应的数据库和 NPC 设定
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const sessionConfig = reactive({
  world_name: '',
  npc_name: '',
  npc_level: 1,
  player_id: 'test_player_001', 
})

// ====== 状态管理 (响应式数据) ======
// 从后端获取的预设 NPC 列表
const presetNpcs = ref([])
// 存放可用的剧本列表
const availableWorlds = ref([]) 
// 输入框绑定的文本
const inputText = ref('')
// 聊天记录
const chatHistory = ref([])
// 加载状态
const isLoading = ref(false)
// 记忆提炼状态
const isDistilling = ref(false)
// 用于存放图片传给后端视觉模型后，返回的特征 ID
const currentAttachmentId = ref(null)

// ====== 核心函数 ======
// ====== TODO: 多模态视觉通道 (使用 Axios) ======
// 当用户选择了图片并触发上传时执行
const handleImageUpload = async (options) => {
  ElMessage.info('视觉接口暂未开通！')
}

// 监听玩家 ID 或 NPC 切换时，可以选择清空当前屏幕的对话历史
const clearChat = () => {
  chatHistory.value = []
  ElMessage.success('已切换测试环境，聊天记录已清空')
}

// 这里和 Persona.vue 中一致
const fetchWorlds = async () => {
  try {
    const res = await fetch(`${API_BASE}/worlds/list`)
    const data = await res.json()
    availableWorlds.value = data.worlds
    if (data.worlds && data.worlds.length > 0) {
      sessionConfig.world_name = data.worlds[0] // 默认选中第一个
    }
  } catch (error) {
    console.error('获取剧本列表失败', error)
  }
}

// 后端扫描拉取已经生成的NPC JSON 列表
const fetchPresets = async (world = '') => {
  try {
    const url = world ? `${API_BASE}/sandbox/presets?world_name=${world}` : `${API_BASE}/sandbox/presets`
    const res = await fetch(url)
    const data = await res.json()
    presetNpcs.value = data.npcs
  } catch (error) {
    console.error('获取NPC列表失败', error)
  }
}

// 监听剧本变化
watch(() => sessionConfig.world_name, (newWorld) => {
  if (newWorld) {
    fetchPresets(newWorld)
    sessionConfig.npc_name = '' // 清空不匹配的NPC
    sessionConfig.npc_level = 1
    clearChat()
  }
})

// 用户在下拉框选中一个存在的 NPC 时，自动同步其 Level
const handleNpcChange = (val) => {
  const found = presetNpcs.value.find(n => n.value === val)
  if (found) {
    sessionConfig.npc_level = found.level
  }
  clearChat() 
}

onMounted(async () => {
  await fetchWorlds() // 页面加载时获取剧本和NPC预设
})

// ====== 记忆提炼 (LTM) 请求 ======
const distillMemory = async () => {
  if (!sessionConfig.player_id || !sessionConfig.npc_name) {
    ElMessage.warning('请先填写完整的玩家ID和NPC名称')
    return
  }
  isDistilling.value = true
  try {
    const response = await fetch(`${API_BASE}/memory/distill`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        player_id: sessionConfig.player_id,
        npc_name: sessionConfig.npc_name
      })
    })
    const data = await response.json()
    if (response.ok) {
      ElMessage.success(data.msg || '记忆提炼成功')
    } else {
      ElMessage.warning(data.msg || '提炼被跳过')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('记忆提炼接口调用失败，请检查后端引擎')
  } finally {
    isDistilling.value = false
  }
}

// ====== 流式对话通道 (使用原生 Fetch) ======
const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text) return
  
  // 玩家发言上屏
  chatHistory.value.push({ role: 'user', content: text })
  inputText.value = '' 
  isLoading.value = true 

  // 预占空壳气泡
  const npcMessageIndex = chatHistory.value.length
  chatHistory.value.push({ role: 'npc', content: '' })

  try {
    // 动态读取网页上填写的名字和等级，发给后端
    const response = await fetch(`${API_BASE}/chat_stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        world_name: sessionConfig.world_name,
        npc_name: sessionConfig.npc_name,
        npc_level: Number(sessionConfig.npc_level), // 确保发过去的是数字
        player_id: sessionConfig.player_id,
        player_message: text,
        attachment_id: null
      })
    })

    if (!response.ok) throw new Error(`HTTP Error: ${response.status}`)

    // 流式解析
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      // 将二进制解码为字符串
      const chunk = decoder.decode(value, { stream: true })
      
      // 按行切分开，只把真实数据拼进去
      const lines = chunk.split('\n')
      for (const line of lines) {
        if (line.startsWith('data:')) {
          // 截取并清理数据
          const text = line.substring(5).trimStart()
          
          if (text && text !== '[DONE]') {
            // 如果发现是metadata的指令，直接丢弃（或这里log拦截掉），不上屏
            if (text.startsWith('{') && text.includes('"meta"')) {
              console.log("网页端拦截到隐藏动作指令:", text);
              continue; 
            }
            
            // 恢复换行符（如果后端转义了的话）
            const displayText = text.replace(/\\n/g, '\n');
            // 正常的文本台词，追加到聊天气泡
            chatHistory.value[npcMessageIndex].content += displayText;
          }
        }
      }
    }

  } catch (error) {
    console.error('流式通信失败:', error)
    chatHistory.value[npcMessageIndex].content = '（引擎连接中断，请检查 FastAPI 状态）'
  } finally {
    isLoading.value = false 
  }
}

</script>

<template>
  <div class="sandbox-container">
    <!-- 顶部控制台：自由输入区 -->
    <el-card class="status-bar" shadow="hover">
      <div class="config-row">
        <div class="config-item">
          <span class="label">测试人员 ID:</span>
          <el-input v-model="sessionConfig.player_id" size="small" style="width: 140px" @change="clearChat" />
        </div>
        <div class="config-item">
          <span class="label">世界观:</span>
          <el-select v-model="sessionConfig.world_name" size="small" style="width: 140px">
            <el-option v-for="w in availableWorlds" :key="w" :label="w" :value="w" />
          </el-select>
        </div>
        <!-- 加入下拉预设 -->
        <div class="config-item">
          <span class="label">目标 NPC:</span>
          <el-select 
            v-model="sessionConfig.npc_name" 
            size="small" 
            style="width: 160px"
            filterable
            allow-create
            default-first-option
            placeholder="选择或直接输入"
            @change="handleNpcChange"
          >
            <el-option 
              v-for="npc in presetNpcs" 
              :key="npc.value" 
              :label="npc.label" 
              :value="npc.value" 
            />
          </el-select>
        </div>
        
        <div class="config-item">
          <span class="label">权限等级:</span>
          <el-input-number v-model="sessionConfig.npc_level" :min="1" :max="10" size="small" style="width: 100px" />
        </div>
        <div class="status-indicator">
          <el-tag type="success" effect="dark">就绪</el-tag>
        </div>
      </div>
    </el-card>

    <!-- 对话流区域 -->
    <el-card class="chat-area" shadow="hover">
      <div class="message-list">
        <div class="message system-msg">
          <p>系统：您可以在顶部随时切换测试目标或自由输入新标识。</p>
        </div>

        <div 
          v-for="(msg, index) in chatHistory" 
          :key="index" 
          :class="['message', msg.role === 'user' ? 'user-message' : 'npc-message']"
        >
          <div class="avatar">{{ msg.role === 'user' ? '我' : 'NPC' }}</div>
          <div class="bubble">{{ msg.content }}</div>
        </div>
      </div>
    </el-card>

    <!-- 底部输入与控制区域 -->
    <div class="input-area">
      <el-button type="primary" plain :icon="Picture" @click="handleImageUpload">图片上传</el-button>

      <el-input
        v-model="inputText"
        placeholder="输入指令或剧情对话..."
        class="text-input"
        @keyup.enter="sendMessage"
        :disabled="isLoading"
      />

      <el-button type="primary" :icon="Position" :loading="isLoading" @click="sendMessage">
        {{ isLoading ? '推理中...' : '发送' }}
      </el-button>
      <el-button type="warning" :icon="Coin" plain :loading="isDistilling" @click="distillMemory">记忆提炼</el-button>
    </div>
  </div>
</template>

<style scoped>
.sandbox-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 16px;
}

/* 顶部配置栏样式 */
.status-bar { border-radius: 8px; }
.config-row { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.config-item { display: flex; align-items: center; gap: 8px; }
.config-item .label { font-size: 14px; font-weight: bold; color: #606266; }
.status-indicator { margin-left: auto; }

/* 聊天区域样式 */
.chat-area { flex: 1; overflow-y: auto; border-radius: 8px; background-color: #fafafa; }
.message-list { padding: 10px; }
.system-msg { color: #909399; font-size: 13px; text-align: center; margin-bottom: 10px; }

/* 底部输入框样式 */
.input-area {
  display: flex; gap: 10px; align-items: center;
  background: white; padding: 16px; border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}
.text-input { flex: 1; }

/* 气泡布局 */
.message {
  display: flex; margin-bottom: 20px; align-items: flex-start;
  width: 100%; box-sizing: border-box;
}
.user-message { flex-direction: row-reverse; }

.avatar {
  width: 40px; height: 40px; border-radius: 50%;
  background-color: #409eff; color: white;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; margin: 0 10px; flex-shrink: 0;
}
.npc-message .avatar { background-color: #67c23a; }

.bubble {
  max-width: 70%; padding: 12px 16px; border-radius: 8px;
  background-color: white; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  line-height: 1.5; word-wrap: break-word; white-space: pre-wrap;
}
.user-message .bubble { background-color: #ecf5ff; }
</style>