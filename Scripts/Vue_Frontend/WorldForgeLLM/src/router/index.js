import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      // 默认打开网页时，重定向到沙盒
      path: '/',
      redirect: '/sandbox' 
    },
    {
      path: '/sandbox',
      name: 'sandbox',
      // TODO: 对接 FastAPI 的流式对话接口和图片 Base64 上传
      component: () => import('../views/Sandbox.vue')
    },
    {
      path: '/persona',
      name: 'persona',
      // TODO: 渲染 Element Plus 的表单，一键生成 JSON
      component: () => import('../views/Persona.vue')
    },
    {
      path: '/world',
      name: 'world',
      // TODO: 放置文件拖拽上传组件，对接 LangGraph 和 ChromaDB
      component: () => import('../views/WorldForge.vue')
    }
  ]
})

export default router
