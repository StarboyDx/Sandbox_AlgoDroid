<script setup>
import { ref, reactive, onMounted } from 'vue'
import { MagicStick } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// 从后端获取可选的世界列表（知识库）
const worldOptions = ref([])
const selectedWorld = ref('')

const userPrompt = ref('')
const isLoading = ref(false)

// 页面右侧用于展示最终生成的 JSON
const generatedAsset = ref(null)

// 页面加载时获取世界列表
const fetchWorlds = async () => {
  try {
    const res = await fetch('http://localhost:8000/api/v1/worlds/list')
    const data = await res.json()
    worldOptions.value = data.worlds
    if (data.worlds.length > 0) {
      selectedWorld.value = data.worlds[0]
    }
  } catch (e) {
    ElMessage.error('获取世界观列表失败')
  }
}

onMounted(() => {
  fetchWorlds()
})

// 触发后端的 LangGraph 工作流
const generateAndSave = async () => {
  if (!userPrompt.value.trim()) {
    ElMessage.warning('请先输入 NPC 的需求描述')
    return
  }
  
  isLoading.value = true
  generatedAsset.value = null // 清空旧数据
  
  try {
    const response = await fetch('http://localhost:8000/api/v1/admin/generate_persona', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        world_name: selectedWorld.value,
        user_prompt: userPrompt.value
      })
    })
    
    const data = await response.json()
    if (data.status === 'success') {
      if (!data.message || data.message.includes('❌')) {
         ElMessage.error("审核多次未通过，强制终止并丢弃数据！")
      } else {
         generatedAsset.value = data.generated_data
         ElMessage.success(data.message)
      }
    } else {
      ElMessage.error('生成流程中断')
    }
  } catch (error) {
    ElMessage.error('引擎网关连接失败')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="persona-container">
    <div class="left-panel">
      <el-card shadow="hover" class="box-card">
        <template #header>
          <div class="card-header">
            <span>🎭 资产生成 (Agentic Workflow)</span>
          </div>
        </template>
        
        <div class="form-section">
          <span class="label">1. 指定知识库 (World)：</span>
          <el-select v-model="selectedWorld" size="default" style="width: 200px">
            <el-option v-for="w in worldOptions" :key="w" :label="w" :value="w" />
          </el-select>
        </div>

        <div class="form-section" style="margin-top: 20px;">
          <span class="label">2. NPC 灵感与需求：</span>
          <el-input 
            v-model="userPrompt" 
            type="textarea" 
            :rows="6" 
            placeholder="例如：基于当前世界，给我设计一个叫 Alex 的黑市商人，等级为 3。要求带有贪婪的属性。" 
            style="margin-top: 10px;"
          />
        </div>

        <el-button 
          type="primary" 
          :icon="MagicStick" 
          size="large" 
          @click="generateAndSave" 
          :loading="isLoading"
          style="margin-top: 30px; width: 100%;"
        >
          {{ isLoading ? '执行中 (检索 -> 循环验证 -> MCP存储)...' : '执行全自动生成入库' }}
        </el-button>
      </el-card>
    </div>

    <div class="right-panel">
      <el-card shadow="never" class="json-card">
        <template #header>
          <div style="font-weight: bold; color: #409EFF;">📦 最终入库资产 (已验证)</div>
        </template>
        <div v-if="generatedAsset">
          <pre class="code-block">{{ JSON.stringify(generatedAsset, null, 2) }}</pre>
        </div>
        <div v-else class="empty-state">
          等待生成流程结束...
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.persona-container { display: flex; gap: 20px; max-width: 1000px; margin: 0 auto; padding-top: 20px; }
.left-panel { flex: 5; }
.right-panel { flex: 5; }

.box-card { height: 100%; border-radius: 8px; }
.card-header { font-size: 18px; font-weight: bold; color: #303133; }
.label { font-size: 14px; font-weight: bold; color: #606266; }

.json-card { height: 100%; background: #fafafa; border-radius: 8px; }
.code-block { background: #282c34; color: #abb2bf; padding: 15px; border-radius: 8px; overflow-x: auto; font-family: 'Courier New', monospace; line-height: 1.5; font-size: 14px;}
.empty-state { text-align: center; color: #909399; margin-top: 50px; font-size: 14px; }
</style>