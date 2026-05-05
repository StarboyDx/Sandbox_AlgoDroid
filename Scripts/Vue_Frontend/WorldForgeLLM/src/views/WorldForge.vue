<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { Link, Picture, DocumentChecked, UploadFilled, MagicStick, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// ==========================================
// 核心状态管理 
// ==========================================
const session = reactive({
  id: 'test_player_001', // 默认id
  world_name: '',   // 当前选中的剧本
  inputText: '',     // 用户输入的文字
  use_rag: false    // 默认关闭知识库关联
})

const availableWorlds = ref([]) // 可用剧本列表
const chatHistory = ref([])     // 聊天记录数组
const isLoading = ref(false)    // 控制发送按钮的 loading 状态
const chatContainer = ref(null) // 用于控制聊天窗口滚动条的 DOM 引用

// 文件上传相关状态
const selectedFile = ref(null)  // 当前选中的文件对象
const filePreview = ref(null)   // 文件预览状态 (图片是 base64 url，其他是类别字符串)
// 热更新剧本相关选项
const loreDialogVisible = ref(false) // 控制弹窗显示
const editingLore = ref('')          // 正在编辑的设定内容
const currentLevel = ref(1)          // 世界权限等级可选

// 初始化
onMounted(async () => {
  try {
    const res = await fetch('http://localhost:8000/api/v1/worlds/list') 
    const data = await res.json()
    availableWorlds.value = data.worlds || ['Valoria', 'CyberCity'] // 容错兜底
    
    // 默认选第一个剧本
    if (availableWorlds.value.length > 0) {
      session.world_name = availableWorlds.value[0]
    }
  } catch (error) {
    ElMessage.warning('未能连接到服务器拉取剧本列表，使用本地测试数据')
    availableWorlds.value = ['Valoria']
    session.world_name = 'Valoria'
  }
})

// ==========================================
// UI 交互逻辑
// ==========================================

// 滚动到聊天窗口最底部
const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

// 处理用户选择文件
const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (!file) return
  
  // 大小限制：50MB (根据实际需求调整)
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('附件请限制在 50MB 以内')
    return
  }
  
  selectedFile.value = file
  
  // 判断文件类型，决定预览区的 UI 表现
  if (file.type.startsWith('image/')) {
    filePreview.value = URL.createObjectURL(file) // 图片直接显示略缩图
  } else if (file.type.startsWith('video/')) {
    filePreview.value = 'is_video'
  } else if (file.type.startsWith('audio/')) {
    filePreview.value = 'is_audio'
  } else {
    filePreview.value = 'is_document' // TXT, PDF 等文档
  }
  // 选择完后清空输入框，避免重复上传同一文件时不触发 change 事件
  event.target.value = ''
}

// ==========================================
// 发送聊天 & 多模态通信
// ==========================================
const sendMessage = async () => {
  // 防呆：没打字也没传文件，直接 return
  if (!session.inputText.trim() && !selectedFile.value) return

  // 组装前端显示的 Message 对象
  const userMessage = {
    role: 'user',
    content: session.inputText || '请分析这份参考材料并进行剧本推演。', // 给没打字只传文件的场景一个默认文案
    isImage: selectedFile.value?.type.startsWith('image/'),
    filePreviewUrl: filePreview.value === 'is_document' || filePreview.value === 'is_video' || filePreview.value === 'is_audio' ? null : filePreview.value,
    fileName: selectedFile.value?.name,
    fileCategory: filePreview.value // 记录一下类别用于显示不同 icon
  }
  
  // 先把用户的话推上屏幕
  chatHistory.value.push(userMessage)
  scrollToBottom()

  // 组装发给后端的 FormData tip：这里和之前传json不一样了，因为要传文件，所以必须用 FormData
  const formData = new FormData()
  formData.append('session_id', session.id)
  formData.append('world_name', session.world_name)
  formData.append('prompt', userMessage.content)
  formData.append('use_rag', session.use_rag) // 是否关联知识库开关状态给后端
  if (selectedFile.value) {
    formData.append('file', selectedFile.value)
  }

  // 清理输入框，进入 Loading
  session.inputText = ''
  selectedFile.value = null
  filePreview.value = null
  isLoading.value = true

  // 发起网络请求
  try {
    const res = await fetch('http://localhost:8000/api/v1/worldforge/chat', {
      method: 'POST',
      body: formData // 浏览器会自动加上 multipart/form-data 的 header 和 boundary
    })
    
    const data = await res.json()
    if (res.ok) {
      // 成功，将 AI 的回复推上屏幕
      chatHistory.value.push({ 
        role: 'ai', 
        content: data.reply, 
        engine: data.engine // 后端用什么引擎回答的，显示在气泡底部
      })
    } else {
      throw new Error(data.detail)
    }
  } catch (error) {
    ElMessage.error('多模态网关异常: ' + error.message)
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

// 热更新入库，入库前可以自行编辑
const openLoreEditDialog = (content) => {
  editingLore.value = content // AI 回复填进编辑框
  loreDialogVisible.value = true
}
// 确认入库
const confirmSaveLore = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/v1/worldforge/save_lore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        world_name: session.world_name, 
        content: editingLore.value, // 发送修改后的
        level: currentLevel.value 
      })
    })
    const data = await res.json()
    if (res.ok) {
      ElMessage.success('剧本热更新完成！')
      loreDialogVisible.value = false // 关弹窗
    } else throw new Error(data.detail)
  } catch (error) {
    ElMessage.error('入库失败: ' + error.message)
  }
}
</script>

<template>
  <div class="forge-layout">
    <div class="chat-section">
      
      <!-- 顶部控制栏 -->
      <div class="glass-header">
        <div class="header-brand">
          <el-icon :size="24" color="#409EFF"><MagicStick /></el-icon>
          <h2>自由创作</h2>
        </div>
        
        <!-- 动态配置区：id + 剧本选择，这里ID相当于一个会话标识，后端redis存着的，要换对话就更换id -->
        <div class="header-controls">
          <el-input v-model="session.id" placeholder="操作者 ID" style="width: 140px;">
            <template #prepend>ID</template>
          </el-input>

          <el-select v-model="session.world_name" placeholder="选择或输入新剧本" filterable allow-create default-first-option style="width: 160px;">
            <el-option v-for="world in availableWorlds" :key="world" :label="world" :value="world" />
          </el-select>
        </div>
      </div>

      <!-- 核心聊天窗口 -->
      <div class="chat-window scrollbar-hide" ref="chatContainer">
        
        <!-- 初始空状态引导 -->
        <div v-if="chatHistory.length === 0" class="empty-state">
          <el-icon :size="60" color="#DCDFE6"><UploadFilled /></el-icon>
          <h3>和 AI 互动自由创作剧本</h3>
          <p>支持上传文件进行创作，你的 ID 相当于一个会话，更换 ID（或剧本）即可开始新对话。</p>
        </div>

        <!-- 消息列表循环 -->
        <div v-for="(msg, idx) in chatHistory" :key="idx" :class="['message-box', msg.role]">
          <div class="avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
          
          <div class="content-body">
            <!-- 【渲染附件区域】 -->
            <div v-if="msg.fileName" class="attachment-bubble">
               <!-- 如果是图片，直接渲染 -->
               <img v-if="msg.isImage" :src="msg.filePreviewUrl" class="msg-image" />
               <!-- 如果是文档/音视频，渲染一个小卡片 -->
               <div v-else class="doc-file">
                 <el-icon><Link /></el-icon> 
                 <span>{{ msg.fileName }}</span>
                 <span class="file-tag">{{ msg.fileCategory.replace('is_', '') }}</span>
               </div>
            </div>

            <!-- 【渲染文本气泡区域】 -->
            <div class="text-bubble">
              {{ msg.content }}
              
              <!-- 【渲染 AI 专属的热更新操作区】 -->
              <div v-if="msg.role === 'ai'" class="action-footer">
                <span class="engine-badge">⚡ {{ msg.engine }}</span>
                <!-- 核心：采纳按钮 -->
                <el-button type="primary" link size="small" :icon="DocumentChecked" @click="openLoreEditDialog(msg.content)">
                  采纳设定并热更新至 RAG 库
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部输入控制台 -->
      <div class="console-input-area">
        <!-- 隐藏的真实文件输入框 -->
        <input type="file" ref="fileInput" accept="image/*,audio/*,video/*,.txt,.pdf" style="display: none" @change="handleFileSelect" />
        
        <!-- 待发送附件暂存区 (选中文件后，这里会显示一下) -->
        <transition name="el-zoom-in-bottom">
          <div v-if="selectedFile" class="staging-area">
             <!-- 图片预览 -->
             <img v-if="filePreview && filePreview !== 'is_document' && filePreview !== 'is_video' && filePreview !== 'is_audio'" :src="filePreview" class="tiny-preview"/>
             <!-- 文档/多媒体文字提示 -->
             <span v-else class="staging-text">📎 {{ selectedFile.name }} ({{ (selectedFile.size/1024/1024).toFixed(1) }}MB)</span>
             <el-button circle size="small" type="danger" :icon="Close" class="remove-btn" @click="selectedFile = null; filePreview = null" />
          </div>
        </transition>

        <!-- 输入框行 -->
        <div class="input-row">
          <!-- 触发文件上传的按钮 -->
          <el-button color="#2B2F3A" dark :icon="Picture" @click="$refs.fileInput.click()">
            附加文件
          </el-button>
          
          <!-- 知识库关联开关 -->
          <el-switch 
            v-model="session.use_rag" 
            active-text="关联剧本" 
            style="margin: 0 10px; flex-shrink: 0; white-space: nowrap;" 
          />

          <el-input
            v-model="session.inputText"
            placeholder="输入对话内容，或上传文件进行创作..."
            @keyup.enter="sendMessage"
            :disabled="isLoading"
            class="main-input"
          />
          
          <!-- 发送按钮 -->
          <el-button type="primary" @click="sendMessage" :loading="isLoading" style="width: 100px;">
            发送
          </el-button>
        </div>
      </div>
    </div>
    <!-- 设定入库二次编辑弹窗 -->
    <el-dialog v-model="loreDialogVisible" title="审查并编辑世界观设定" width="50%">
      <div style="margin-bottom: 10px; color: #606266; font-size: 13px;">
        请剔除 AI 说的废话（如"好的，为您生成"），仅保留纯粹的世界观干货，以免污染知识库。
      </div>
      <!-- 权限选择 -->
      <div style="margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
        <span>设定密级：</span>
        <el-input-number v-model="currentLevel" :min="1" :max="99" size="small" placeholder="手动输入权限等级" />
      </div>
      <!-- 文本编辑器 -->
      <el-input v-model="editingLore" type="textarea" :rows="10" placeholder="整理你的完美设定..." />
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="loreDialogVisible = false">取 消</el-button>
          <el-button type="primary" @click="confirmSaveLore">确认热更新 (写入 ChromaDB)</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* ==========================================
   极其精致的现代极客风样式 (直接复用并增强)
   ========================================== */
.forge-layout { 
  height: 100vh; /* 撑满屏幕高度，方便测试 */
  display: flex; 
  background: #F2F4F7; 
  padding: 20px;
  box-sizing: border-box;
}

.chat-section { 
  flex: 1; 
  display: flex; 
  flex-direction: column; 
  background: #FFFFFF; 
  border-radius: 16px; 
  box-shadow: 0 8px 24px rgba(0,0,0,0.04);
  overflow: hidden;
}

.glass-header { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  padding: 16px 24px; 
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #E4E7ED; 
  z-index: 10;
}

.header-brand { display: flex; align-items: center; gap: 12px; }
.header-brand h2 { margin: 0; font-size: 18px; font-weight: 600; color: #303133; }
.header-controls { display: flex; gap: 12px; align-items: center; }

.chat-window { 
  flex: 1; 
  padding: 24px; 
  overflow-y: auto; 
  background: #FAFBFC; 
}

.empty-state { 
  height: 100%; 
  display: flex; 
  flex-direction: column; 
  align-items: center; 
  justify-content: center; 
  color: #909399; 
}
.empty-state h3 { margin: 16px 0 8px; color: #606266; font-weight: 500; }

.message-box { display: flex; gap: 16px; margin-bottom: 32px; }
.message-box.user { flex-direction: row-reverse; }

.avatar { 
  width: 42px; height: 42px; 
  border-radius: 12px; 
  display: flex; align-items: center; justify-content: center; 
  font-weight: 700; font-size: 16px; flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.message-box.user .avatar { background: #2B2F3A; color: #FFF; }
.message-box.ai .avatar { background: linear-gradient(135deg, #409EFF, #36D1DC); color: #FFF; }

.content-body { max-width: 75%; display: flex; flex-direction: column; gap: 8px; }
.message-box.user .content-body { align-items: flex-end; }

/* 附件渲染样式 */
.attachment-bubble { margin-bottom: 4px; }
.msg-image { 
  max-width: 300px; 
  border-radius: 12px; 
  box-shadow: 0 4px 12px rgba(0,0,0,0.1); 
  border: 2px solid #FFF;
}
.doc-file { 
  padding: 10px 14px; 
  background: #F4F4F5; 
  border-radius: 8px; 
  font-size: 14px; 
  color: #303133; 
  display: inline-flex; 
  align-items: center; 
  gap: 8px;
  border: 1px solid #E4E7ED;
}
.file-tag { font-size: 11px; background: #E4E7ED; padding: 2px 6px; border-radius: 4px; color: #909399; }

/* 文本气泡样式 */
.text-bubble { 
  padding: 16px 20px; 
  border-radius: 12px; 
  line-height: 1.6; 
  font-size: 15px; 
  white-space: pre-wrap; 
  word-wrap: break-word;
}
.message-box.user .text-bubble { 
  background: #EBF5FF; 
  color: #1A365D; 
  border-bottom-right-radius: 4px;
}
.message-box.ai .text-bubble { 
  background: #FFF; 
  color: #303133; 
  border: 1px solid #E4E7ED;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

/* 采纳热更新 Footer */
.action-footer { 
  margin-top: 14px; 
  padding-top: 12px; 
  border-top: 1px dashed #E4E7ED; 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
}
.engine-badge { font-size: 12px; color: #909399; background: #F4F4F5; padding: 4px 8px; border-radius: 6px; font-family: monospace;}

/* 底部输入区 */
.console-input-area { 
  padding: 20px 24px; 
  background: #FFF; 
  border-top: 1px solid #E4E7ED; 
}

/* 暂存区样式 */
.staging-area { 
  display: inline-flex; 
  align-items: center; 
  margin-bottom: 12px; 
  padding: 8px 12px; 
  background: #F4F4F5; 
  border-radius: 8px; 
  border: 1px solid #E4E7ED;
  position: relative;
}
.tiny-preview { height: 48px; border-radius: 6px; margin-right: 12px; border: 1px solid #DCDFE6; }
.staging-text { font-size: 13px; color: #606266; margin-right: 16px; }
.remove-btn { position: absolute; right: -10px; top: -10px; transform: scale(0.8); }

.input-row { display: flex; gap: 12px; }
.main-input { 
  flex: 1; /* 让输入框自动吸纳所有剩余的宽度 */
}
.main-input :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px #DCDFE6 inset; background: #F4F4F5; }
.main-input :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #409EFF inset; background: #FFF; }

.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>