<template>
  <div class="vector-page">
    <div class="vector-header">
      <div>
        <h2 class="page-title">向量库管理</h2>
        <p class="page-subtitle">
          管理岗位向量入库情况，支持补齐未入库岗位、查看原始文本、相似岗位搜索和批量重嵌入。
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshAll" :loading="refreshing">刷新</el-button>
        <el-button type="primary" plain @click="embedAll" :loading="embeddingAll">导入全部未入库岗位</el-button>
        <el-button type="primary" @click="reembedAll" :loading="reembeddingAll">一键重嵌入全部已发布岗位</el-button>
      </div>
    </div>

    <el-alert
      v-if="queueMessage"
      :title="queueMessage"
      type="success"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :lg="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-hint">{{ card.hint }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :lg="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>向量总览</span>
              <span class="card-tip">已入库 / 未入库岗位都可在这里查看</span>
            </div>
          </template>

          <el-tabs v-model="activeTab">
            <el-tab-pane label="已入库岗位" name="embedded">
              <div class="table-toolbar">
                <el-input
                  v-model="embeddedSearchText"
                  placeholder="搜索岗位名称"
                  clearable
                  @keyup.enter="fetchEmbeddedJobs"
                  style="max-width: 280px"
                >
                  <template #prefix><el-icon><Search /></el-icon></template>
                </el-input>
                <el-button type="primary" plain @click="fetchEmbeddedJobs">查询</el-button>
              </div>

              <el-table :data="embeddedJobs" v-loading="embeddedLoading" empty-text="暂无已入库岗位">
                <el-table-column type="index" label="序号" width="70" />
                <el-table-column prop="title" label="岗位名称" min-width="140" show-overflow-tooltip />
                <el-table-column label="JD全文" width="90">
                  <template #default="{ row }">
                    <el-tag :type="row.has_jd_full ? 'success' : 'info'" size="small">
                      {{ row.has_jd_full ? "已入库" : "缺失" }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="关键词" width="90">
                  <template #default="{ row }">
                    <el-tag :type="row.has_jd_keywords ? 'success' : 'info'" size="small">
                      {{ row.has_jd_keywords ? "已入库" : "缺失" }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="标题向量" width="96">
                  <template #default="{ row }">
                    <el-tag :type="row.has_jd_title ? 'success' : 'warning'" size="small">
                      {{ row.has_jd_title ? "已入库" : "预留" }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="updated_at" label="最近嵌入时间" width="170">
                  <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="360" fixed="right">
                  <template #default="{ row }">
                    <div class="action-row">
                      <el-button size="small" @click="openContentDialog(row)" :loading="viewingJobId === row.job_id">
                        查看内容
                      </el-button>
                      <el-button size="small" @click="openSimilarDialog(row)" :loading="similarJobId === row.job_id">
                        相似岗位
                      </el-button>
                      <el-button size="small" @click="reEmbedJob(row.job_id)" :loading="embeddingJobId === row.job_id">
                        重新嵌入
                      </el-button>
                      <el-button size="small" type="danger" @click="deleteEmbedding(row.job_id)" :loading="deletingJobId === row.job_id">
                        删除
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>

              <el-pagination
                v-if="embeddedPagination.total > embeddedPagination.page_size"
                style="margin-top: 16px; justify-content: flex-end"
                background
                layout="prev, pager, next"
                :total="embeddedPagination.total"
                :page-size="embeddedPagination.page_size"
                v-model:current-page="embeddedPagination.page"
                @current-change="fetchEmbeddedJobs"
              />
            </el-tab-pane>

            <el-tab-pane label="未入库岗位" name="unembedded">
              <div class="table-toolbar">
                <el-input
                  v-model="unembeddedSearchText"
                  placeholder="搜索未入库岗位"
                  clearable
                  @keyup.enter="fetchUnembeddedJobs"
                  style="max-width: 280px"
                >
                  <template #prefix><el-icon><Search /></el-icon></template>
                </el-input>
                <el-button type="primary" plain @click="fetchUnembeddedJobs">查询</el-button>
              </div>

              <el-table :data="unembeddedJobs" v-loading="unembeddedLoading" empty-text="暂无未入库岗位">
                <el-table-column type="index" label="序号" width="70" />
                <el-table-column prop="title" label="岗位名称" min-width="180" show-overflow-tooltip />
                <el-table-column prop="status" label="状态" width="100" />
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="140" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" @click="reEmbedJob(row.job_id)" :loading="embeddingJobId === row.job_id">
                      立即嵌入
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-pagination
                v-if="unembeddedPagination.total > unembeddedPagination.page_size"
                style="margin-top: 16px; justify-content: flex-end"
                background
                layout="prev, pager, next"
                :total="unembeddedPagination.total"
                :page-size="unembeddedPagination.page_size"
                v-model:current-page="unembeddedPagination.page"
                @current-change="fetchUnembeddedJobs"
              />
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="contentDialogVisible" title="岗位原始文本内容" width="900px">
      <template v-if="embeddingDetail">
        <div v-for="item in embeddingDetail.items" :key="item.embedding_type" class="content-block">
          <div class="content-header">
            <span>{{ embeddingTypeLabelMap[item.embedding_type] || item.embedding_type }}</span>
            <el-tag size="small">{{ item.model_name }} / {{ item.dim }}维</el-tag>
          </div>
          <div class="content-text">{{ item.content_text }}</div>
          <div class="content-meta">最近更新时间：{{ formatDate(item.updated_at) }}</div>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="similarDialogVisible" title="相似岗位搜索结果" width="760px">
      <el-table :data="similarJobs" empty-text="暂无相似岗位结果">
        <el-table-column type="index" label="序号" width="70" />
        <el-table-column prop="job_title" label="岗位名称" min-width="240" show-overflow-tooltip />
        <el-table-column prop="similarity" label="相似度" width="120">
          <template #default="{ row }">
            {{ Math.round((row.similarity || 0) * 100) }}%
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  hrDeleteJobEmbedding,
  hrEmbedAllJobs,
  hrEmbedJob,
  hrGetEmbeddedJobs,
  hrGetJobEmbeddingDetail,
  hrGetSimilarJobs,
  hrGetUnembeddedJobs,
  hrGetVectorStats,
  hrReembedAllJobs,
} from "../../api/index.js";

const embeddingTypeLabelMap = {
  jd_full: "JD 全文",
  jd_keywords: "关键词拼接",
  jd_title: "岗位标题",
};

const stats = reactive({
  total_vectors: 0,
  embedded_jobs: 0,
  by_type: {
    jd_full: 0,
    jd_keywords: 0,
    jd_title: 0,
  },
  model_name: "-",
  dimension: 0,
  latest_update: null,
});

const activeTab = ref("embedded");
const embeddedSearchText = ref("");
const unembeddedSearchText = ref("");
const embeddedJobs = ref([]);
const unembeddedJobs = ref([]);
const similarJobs = ref([]);
const embeddingDetail = ref(null);
const embeddedLoading = ref(false);
const unembeddedLoading = ref(false);
const refreshing = ref(false);
const embeddingAll = ref(false);
const reembeddingAll = ref(false);
const embeddingJobId = ref("");
const deletingJobId = ref("");
const viewingJobId = ref("");
const similarJobId = ref("");
const queueMessage = ref("");
const contentDialogVisible = ref(false);
const similarDialogVisible = ref(false);

const embeddedPagination = reactive({
  page: 1,
  page_size: 10,
  total: 0,
});

const unembeddedPagination = reactive({
  page: 1,
  page_size: 10,
  total: 0,
});

let pollTimer = null;

const statCards = computed(() => [
  {
    label: "总向量数",
    value: stats.total_vectors,
    hint: `当前共覆盖 ${stats.embedded_jobs} 个岗位`,
  },
  {
    label: "已入库岗位数",
    value: stats.embedded_jobs,
    hint: "至少有一条向量的岗位",
  },
  {
    label: "Embedding 模型",
    value: stats.model_name,
    hint: `向量维度 ${stats.dimension}`,
  },
  {
    label: "最后更新时间",
    value: stats.latest_update ? formatDate(stats.latest_update) : "-",
    hint: "用于观察最近一次入库动作",
  },
]);

const formatDate = (value) => {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
};

const fetchStats = async () => {
  const res = await hrGetVectorStats();
  Object.assign(stats, res.data);
};

const fetchEmbeddedJobs = async () => {
  embeddedLoading.value = true;
  try {
    const res = await hrGetEmbeddedJobs({
      page: embeddedPagination.page,
      page_size: embeddedPagination.page_size,
      search: embeddedSearchText.value,
    });
    embeddedJobs.value = res.data.items || [];
    embeddedPagination.total = res.data.total || 0;
  } finally {
    embeddedLoading.value = false;
  }
};

const fetchUnembeddedJobs = async () => {
  unembeddedLoading.value = true;
  try {
    const res = await hrGetUnembeddedJobs({
      page: unembeddedPagination.page,
      page_size: unembeddedPagination.page_size,
      search: unembeddedSearchText.value,
    });
    unembeddedJobs.value = res.data.items || [];
    unembeddedPagination.total = res.data.total || 0;
  } finally {
    unembeddedLoading.value = false;
  }
};

const refreshAll = async () => {
  refreshing.value = true;
  try {
    await Promise.all([fetchStats(), fetchEmbeddedJobs(), fetchUnembeddedJobs()]);
  } finally {
    refreshing.value = false;
  }
};

const startPolling = (seconds = 30) => {
  let remaining = seconds;
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    remaining -= 2;
    await Promise.all([fetchStats(), fetchEmbeddedJobs(), fetchUnembeddedJobs()]);
    if (remaining <= 0) {
      clearInterval(pollTimer);
      queueMessage.value = "";
    }
  }, 2000);
};

const embedAll = async () => {
  embeddingAll.value = true;
  try {
    const res = await hrEmbedAllJobs();
    queueMessage.value = `已加入 ${res.data.queued_count} 个未入库岗位到向量化队列，页面将自动刷新。`;
    ElMessage.success(queueMessage.value);
    startPolling();
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "批量导入失败");
  } finally {
    embeddingAll.value = false;
  }
};

const reembedAll = async () => {
  reembeddingAll.value = true;
  try {
    const res = await hrReembedAllJobs();
    queueMessage.value = `已加入 ${res.data.queued_count} 个已发布岗位到重嵌入队列，页面将自动刷新。`;
    ElMessage.success(queueMessage.value);
    startPolling();
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "批量重嵌入失败");
  } finally {
    reembeddingAll.value = false;
  }
};

const reEmbedJob = async (jobId) => {
  embeddingJobId.value = jobId;
  try {
    await hrEmbedJob(jobId);
    ElMessage.success("岗位向量已重新生成");
    await refreshAll();
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "重新嵌入失败");
  } finally {
    embeddingJobId.value = "";
  }
};

const deleteEmbedding = async (jobId) => {
  deletingJobId.value = jobId;
  try {
    await hrDeleteJobEmbedding(jobId);
    ElMessage.success("岗位向量已删除");
    await refreshAll();
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "删除向量失败");
  } finally {
    deletingJobId.value = "";
  }
};

const openContentDialog = async (row) => {
  viewingJobId.value = row.job_id;
  try {
    const res = await hrGetJobEmbeddingDetail(row.job_id);
    embeddingDetail.value = res.data;
    contentDialogVisible.value = true;
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "读取原始文本失败");
  } finally {
    viewingJobId.value = "";
  }
};

const openSimilarDialog = async (row) => {
  similarJobId.value = row.job_id;
  try {
    const res = await hrGetSimilarJobs(row.job_id, { top_k: 5 });
    similarJobs.value = res.data.items || [];
    similarDialogVisible.value = true;
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || "查询相似岗位失败");
  } finally {
    similarJobId.value = "";
  }
};

onMounted(refreshAll);
onBeforeUnmount(() => clearInterval(pollTimer));
</script>

<style scoped>
.vector-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vector-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
}

.page-title {
  margin: 0;
}

.page-subtitle {
  margin: 8px 0 0;
  color: #8a94a6;
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-card {
  border-radius: 16px;
}

.stat-label {
  color: #6b7280;
  font-size: 13px;
}

.stat-value {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  color: #16213e;
  word-break: break-word;
}

.stat-hint {
  margin-top: 8px;
  color: #8a94a6;
  font-size: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 600;
}

.card-tip {
  color: #8a94a6;
  font-size: 12px;
}

.table-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.content-block {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #f8fafc;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-weight: 600;
}

.content-text {
  white-space: pre-wrap;
  line-height: 1.7;
  color: #1f2937;
}

.content-meta {
  margin-top: 10px;
  color: #8a94a6;
  font-size: 12px;
}
</style>
