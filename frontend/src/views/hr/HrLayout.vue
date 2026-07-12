<template>
  <el-container class="hr-layout">
    <el-aside width="220px" class="hr-layout__aside">
      <div class="hr-layout__brand">
        <h3 class="hr-layout__title" @click="$router.push('/admin/dashboard')">
          <el-icon><MagicStick /></el-icon> ResumeVane
        </h3>
      </div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#1a1a2e"
        text-color="#999"
        active-text-color="#409EFF"
        class="hr-layout__menu"
      >
        <el-menu-item index="/admin/dashboard">
          <el-icon><DataAnalysis /></el-icon> 工作台
        </el-menu-item>
        <el-menu-item index="/admin/jobs">
          <el-icon><Briefcase /></el-icon> 岗位管理
        </el-menu-item>
        <el-menu-item index="/admin/vectordb">
          <el-icon><DataBoard /></el-icon> 向量库管理
        </el-menu-item>
      </el-menu>

      <div class="hr-layout__footer">
        <span>{{ displayName }}</span>
        <el-button type="danger" text size="small" @click="logout" class="hr-layout__logout">退出</el-button>
      </div>
    </el-aside>

    <el-main class="hr-layout__main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const displayName = "Admin";

onMounted(() => {
  const token = localStorage.getItem("hr_token");
  if (!token) {
    router.push("/admin");
  }
});

const logout = () => {
  localStorage.clear();
  router.push("/admin");
};
</script>

<style scoped>
.hr-layout {
  min-height: 100vh;
  align-items: flex-start;
}

.hr-layout__aside {
  position: sticky;
  top: 0;
  align-self: flex-start;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow-y: auto;
  background: #1a1a2e;
  color: #fff;
}

.hr-layout__brand {
  padding: 20px;
}

.hr-layout__title {
  margin: 0;
  color: #fff;
  cursor: pointer;
}

.hr-layout__menu {
  flex: 1;
  border-right: none;
}

.hr-layout__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #2a2a4a;
  color: #999;
  font-size: 12px;
}

.hr-layout__logout {
  color: #999;
}

.hr-layout__main {
  min-width: 0;
  min-height: 100vh;
  background: #f5f7fa;
}
</style>
