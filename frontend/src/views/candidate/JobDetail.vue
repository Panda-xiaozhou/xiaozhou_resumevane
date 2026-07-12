<template>
  <el-container style="min-height: 100vh; background: #f5f7fa">
    <el-header style="background: #1a1a2e; display: flex; align-items: center; justify-content: space-between">
      <div style="color: #fff; font-size: 22px; font-weight: 700; cursor: pointer" @click="$router.push('/')">
        <el-icon><MagicStick /></el-icon> ResumeVane
      </div>
    </el-header>

    <el-main v-if="job" style="max-width: 800px; margin: 0 auto; width: 100%">
      <el-card>
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span style="font-size: 20px; font-weight: 700">{{ job.title }}</span>
            <el-tag>{{ job.department }}</el-tag>
          </div>
        </template>

        <div style="margin-bottom: 20px">
          <h4>岗位描述</h4>
          <p style="white-space: pre-wrap; color: #333; line-height: 1.8">{{ job.jd_text }}</p>
        </div>

        <div v-if="job.jd_keywords?.length" style="margin-bottom: 24px">
          <h4>技能要求</h4>
          <el-tag v-for="kw in job.jd_keywords" :key="kw" style="margin-right: 8px; margin-bottom: 8px">
            {{ kw }}
          </el-tag>
        </div>

        <el-button type="primary" size="large" @click="$router.push(`/apply/${job.id}`)">
          立即投递
        </el-button>
      </el-card>
    </el-main>

    <el-main v-else-if="loading" style="text-align: center">
      <el-skeleton :rows="8" animated />
    </el-main>

    <el-main v-else style="max-width: 800px; margin: 0 auto; width: 100%">
      <el-empty :description="errorMessage || '岗位不存在或已下架'" />
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getJobDetail } from "../../api/index.js";

const route = useRoute();
const job = ref(null);
const loading = ref(true);
const errorMessage = ref("");

onMounted(async () => {
  try {
    const res = await getJobDetail(route.params.id);
    job.value = res.data;
  } catch (e) {
    errorMessage.value = e?.response?.status === 404 ? "岗位不存在或已下架" : "获取岗位详情失败";
  } finally {
    loading.value = false;
  }
});
</script>
