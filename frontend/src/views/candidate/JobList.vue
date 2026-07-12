<template>
  <el-container style="min-height: 100vh; background: #f5f7fa">
    <el-header style="background: #1a1a2e; display: flex; align-items: center; justify-content: space-between">
      <div style="color: #fff; font-size: 22px; font-weight: 700">
        <el-icon><MagicStick /></el-icon> ResumeVane
      </div>
      <el-button type="primary" size="small" @click="$router.push('/status')">
        查询投递状态
      </el-button>
    </el-header>

    <el-main style="max-width: 960px; margin: 0 auto; width: 100%">
      <h2 style="margin-bottom: 24px">开放岗位</h2>

      <el-empty v-if="jobs.length === 0" description="暂无开放岗位" />

      <el-row :gutter="20">
        <el-col :span="12" v-for="job in jobs" :key="job.id" style="margin-bottom: 20px">
          <el-card shadow="hover" @click="$router.push(`/jobs/${job.id}`)" style="cursor: pointer">
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span style="font-size: 16px; font-weight: 600">{{ job.title }}</span>
                <el-tag size="small" type="success">{{ job.department || '未分类' }}</el-tag>
              </div>
            </template>
            <p style="color: #666; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
              {{ job.jd_text }}
            </p>
            <div style="margin-top: 12px">
              <el-tag v-for="kw in job.jd_keywords" :key="kw" size="small" style="margin-right: 6px">
                {{ kw }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { getPublishedJobs } from "../../api/index.js";

const jobs = ref([]);

onMounted(async () => {
  try {
    const res = await getPublishedJobs();
    jobs.value = res.data;
  } catch (e) {
    console.error("获取岗位列表失败", e);
  }
});
</script>
