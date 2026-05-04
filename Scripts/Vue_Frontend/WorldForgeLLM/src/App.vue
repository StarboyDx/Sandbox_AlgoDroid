<script setup>
import { Cpu } from '@element-plus/icons-vue';

// tip: v-if -> Router
</script>

<template>
  <div class="app-container">
    <el-container class="main-container">
      <!-- 左侧：固定侧边栏 -->
      <el-aside width="240px" class="sidebar">
        <div class="logo-area">
          <el-icon :size="24" color="#409EFC"><Cpu /></el-icon>
          <span class="logo-text">创作中心</span>
        </div>
        <!-- 添加router属性，实现路由跳转，index -> URL -->
        <el-menu
          router 
          :default-active="$route.path"
          class="el-menu-vertical"
          background-color="#2b2f3a"
          text-color="#bfcbd9"
          active-text-color="#409eff"
        >
          <!-- 点击这里，变成/sandbox，右侧自动加载Sandbox组件 -->
          <el-menu-item index="/sandbox">
            <el-icon><ChatDotRound /></el-icon>
            <span>聊天 Chat</span>
          </el-menu-item>
          
          <el-menu-item index="/persona">
            <el-icon><User /></el-icon>
            <span>NPC设定工作台</span>
          </el-menu-item>
          
          <el-menu-item index="/world">
            <el-icon><Document /></el-icon>
            <span>剧本创作</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 右侧：动态内容区 -->
      <el-main class="content-area">
        <!-- tip：这是 Vue Router 的魔法插槽。
             根据左侧点击的 URL，这里会自动渲染对应的 Vue 文件。
             比如 URL 是 /sandbox，这里就会显示 Sandbox.vue 的内容。-->
        <router-view></router-view>
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.app-container {
  height: 100vh;
  width: 100vw;
  margin: 0;
  padding: 0;
  font-family: sans-serif;
}
.main-container {
  height: 100%;
}
.sidebar {
  background-color: #2b2f3a;
  box-shadow: 2px 0 6px rgba(0, 21, 41, .35);
  display: flex;
  flex-direction: column;
}
.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: white;
  font-size: 18px;
  font-weight: bold;
  background-color: #1e222d;
}
.el-menu-vertical {
  border-right: none;
}
.content-area {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>

<style>
body {
  margin: 0;
}
</style>
