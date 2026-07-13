<template>
  <el-container style="min-height: 100vh; background: #f5f7fa">
    <el-header style="background: #1a1a2e; display: flex; align-items: center; justify-content: space-between">
      <div style="color: #fff; font-size: 22px; font-weight: 700; cursor: pointer" @click="$router.push('/')">
        <el-icon><MagicStick /></el-icon> ResumeVane
      </div>
    </el-header>

    <el-main style="max-width: 800px; margin: 0 auto; width: 100%">
      <el-card>
        <template #header>
          <span style="font-size: 18px; font-weight: 600">查询投递状态</span>
        </template>

        <el-form :inline="true">
          <el-form-item label="邮箱">
            <el-input v-model="email" placeholder="请输入投递时使用的邮箱" style="width: 300px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="query" :loading="loading">查询</el-button>
          </el-form-item>
        </el-form>

        <el-table v-if="applications.length > 0" :data="applications" style="margin-top: 20px">
          <el-table-column label="投递时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="job_title" label="岗位" min-width="220" />
          <el-table-column label="状态" width="150">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'pending'" type="info">待筛选</el-tag>
              <el-tag v-else-if="row.status === 'processing'" type="warning">筛选中</el-tag>
              <el-tag v-else-if="row.status === 'passed'" type="success">已通过</el-tag>
              <el-tag v-else-if="row.status === 'pending_review'" type="warning">待复审</el-tag>
              <el-tag v-else-if="row.status === 'screening_failed'" type="danger">筛选失败</el-tag>
              <el-tag v-else type="danger">未通过</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="匹配分" width="100">
            <template #default="{ row }">
              <span v-if="row.match_score > 0">{{ row.match_score }}</span>
              <span v-else style="color: #999">-</span>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="searched && applications.length === 0" description="未找到投递记录" />
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getApplicationStatus } from "../../api/index.js";

const route = useRoute();
const email = ref("");
const applications = ref([]);
const searched = ref(false);
const loading = ref(false);

const formatDate = (value) => {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN");
};

const query = async () => {
  if (!email.value) return;
  loading.value = true;
  searched.value = true;
  try {
    const res = await getApplicationStatus(email.value);
    applications.value = res.data || [];
  } catch (e) {
    applications.value = [];
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  const queryEmail = route.query.email;
  if (typeof queryEmail === "string" && queryEmail) {
    email.value = queryEmail;
    query();
  }
});
</script>
