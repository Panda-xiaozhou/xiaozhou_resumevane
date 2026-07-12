/**
 * ResumeVane 前端 — Vite 构建配置
 * =================================
 * - 开发服务器端口: 3000
 * - API 代理: /api/* → http://localhost:8001 (FastAPI 后端)
 *
 * 启动: npm run dev
 * 构建: npm run build (输出到 dist/)
 */
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  // Vue 3 SFC 编译插件
  plugins: [vue()],

  server: {
    // 前端开发服务器端口
    port: 3000,

    // API 代理——开发环境下将 /api 请求转发到后端
    // 生产环境应改用 Nginx 反代或同域部署
    proxy: {
      "/api": {
        target: "http://localhost:8001",   // FastAPI 后端地址
        changeOrigin: true,                // 修改请求头中的 Origin
      },
    },
  },
});
