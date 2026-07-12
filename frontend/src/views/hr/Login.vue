<template>
  <div class="login-bg">
    <el-card class="login-card" shadow="always">
      <template #header>
        <div class="login-header">
          <h2 class="login-title">
            <el-icon><MagicStick /></el-icon> ResumeVane
          </h2>
          <p class="login-subtitle">智能简历筛选系统</p>
        </div>
      </template>

      <el-form :model="form" :rules="rules" ref="formRef">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" size="large">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" size="large"
            show-password @keyup.enter="onLogin">
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width: 100%; margin-top: 8px" @click="onLogin" :loading="loading">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { hrLogin } from "../../api/index.js";

const router = useRouter();
const loading = ref(false);
const form = reactive({ username: "", password: "" });
const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

const onLogin = async () => {
  loading.value = true;
  try {
    const res = await hrLogin(form.username, form.password);
    const data = res.data;
    localStorage.setItem("hr_token", data.token);
    localStorage.setItem("hr_user_id", data.user_id);
    localStorage.setItem("hr_display_name", data.display_name);
    ElMessage.success("登录成功");
    router.push("/admin/dashboard");
  } catch (e) {
    ElMessage.error("用户名或密码错误");
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-bg {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}
.login-card {
  width: 400px;
  border-radius: 12px;
  border: none;
}
.login-card :deep(.el-card__header) {
  padding-bottom: 0;
  border-bottom: none;
}
.login-header {
  text-align: center;
}
.login-title {
  margin: 0;
  font-size: 24px;
  color: #303133;
}
.login-subtitle {
  color: #909399;
  margin: 8px 0 0;
  font-size: 14px;
}
</style>
