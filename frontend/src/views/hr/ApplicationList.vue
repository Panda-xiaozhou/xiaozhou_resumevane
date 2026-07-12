<template>
  <div class="application-page">
    <div class="page-header">
      <div>
        <el-button class="back-button" @click="$router.push('/admin/jobs')">
          <el-icon><ArrowLeft /></el-icon>
          返回岗位列表
        </el-button>
        <h2 class="page-title">投递列表</h2>
        <p class="page-subtitle">集中查看当前岗位下的投递记录、AI 筛选结果与批量处理状态。</p>
      </div>
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">当前结果</div>
          <div class="summary-value">{{ listSummary.total }}</div>
          <div class="summary-hint">{{ listSummary.resultText }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">待处理</div>
          <div class="summary-value">{{ listSummary.pendingCount }}</div>
          <div class="summary-hint">待筛选记录最适合批量触发处理。</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">已启用筛选</div>
          <div class="summary-filter">{{ listSummary.activeFilterText }}</div>
          <div class="summary-hint">搜索与状态筛选会共同作用于当前列表。</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">默认排序</div>
          <div class="summary-filter">匹配分优先</div>
          <div class="summary-hint">{{ listSummary.sortHint }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="toolbar-card">
      <el-row :gutter="12" class="toolbar-row">
        <el-col :xs="24" :sm="12" :lg="7">
          <el-input v-model="searchText" placeholder="搜索姓名或邮箱..." clearable @keyup.enter="fetchApps">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-col>
        <el-col :xs="24" :sm="8" :lg="5">
          <el-select v-model="filterStatus" placeholder="全部状态" clearable @change="fetchApps" style="width: 100%">
            <el-option label="待筛选" value="pending" />
            <el-option label="筛选中" value="processing" />
            <el-option label="已通过" value="passed" />
            <el-option label="待复审" value="pending_review" />
            <el-option label="未通过" value="rejected" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="4" :lg="3">
          <el-button type="primary" style="width: 100%" @click="fetchApps">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
        </el-col>
        <el-col :xs="24" :lg="9" class="toolbar-actions">
          <el-button
            type="primary"
            plain
            :disabled="selectedApplicationIds.length === 0"
            :loading="selectedBatching"
            @click="rescreenSelected"
          >
            <el-icon><Finished /></el-icon>
            筛选选中项（{{ selectedApplicationIds.length }}）
          </el-button>
          <el-button
            type="warning"
            :disabled="applications.length === 0"
            :loading="batching"
            @click="batchRescreen"
          >
            <el-icon><VideoPlay /></el-icon>
            一键筛选全部（{{ applications.length }}）
          </el-button>
        </el-col>
      </el-row>

      <div class="toolbar-meta">
        <span>状态标签颜色与工作台图表保持一致。</span>
        <span v-if="selectedApplicationIds.length > 0">
          已勾选 {{ selectedApplicationIds.length }} 条，其中可直接处理 {{ selectedPendingIds.length }} 条。
        </span>
      </div>
    </el-card>

    <el-alert
      v-if="selectedApplicationIds.length > 0"
      type="info"
      show-icon
      :closable="false"
      :title="`本次已勾选 ${selectedApplicationIds.length} 条投递，可处理记录 ${selectedPendingIds.length} 条。`"
      description="系统会自动跳过非待筛选状态的记录，避免重复触发不必要的任务。"
    />

    <el-card shadow="never">
      <el-table
        ref="tableRef"
        :data="pagedApps"
        style="width: 100%"
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <template #empty>
          <el-empty :description="emptyDescription" />
        </template>
        <el-table-column type="selection" width="52" />
        <el-table-column label="序号" width="70">
          <template #default="{ $index }">
            {{ getRowIndex($index) }}
          </template>
        </el-table-column>
        <el-table-column label="候选人" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="candidate-name">{{ row.candidate_name }}</div>
            <div class="candidate-time">{{ formatDate(row.created_at) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="candidate_email" label="邮箱" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getApplicationStatusTagType(row.status)">
              {{ getApplicationStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="match_score" label="匹配分" width="96" sortable />
        <el-table-column label="推送" width="110">
          <template #default="{ row }">
            <el-tag
              v-if="hasPushStatusMeta(row.push_status)"
              :type="getPushStatusTagType(row.push_status)"
              size="small"
            >
              {{ getPushStatusLabel(row.push_status) }}
            </el-tag>
            <span v-else class="muted-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="showDetail(row)">详情</el-button>
            <el-button size="small" @click="rescreen(row.id)" :loading="rescreeningId === row.id">重筛</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-pagination
      v-if="sortedApplications.length > pageSize"
      class="pagination"
      background
      layout="prev, pager, next"
      :total="sortedApplications.length"
      :page-size="pageSize"
      v-model:current-page="currentPage"
    />

    <el-dialog v-model="dialogVisible" title="投递详情" width="860px" top="30px">
      <template v-if="detail">
        <div class="detail-overview">
          <div class="detail-overview-item">
            <span class="detail-overview-label">筛选结论</span>
            <el-tag :type="detailStatusMeta.tagType">{{ detailStatusMeta.label }}</el-tag>
          </div>
          <div class="detail-overview-item">
            <span class="detail-overview-label">匹配分</span>
            <strong>{{ detail.match_score ?? "-" }}</strong>
          </div>
          <div class="detail-overview-item">
            <span class="detail-overview-label">推送状态</span>
            <el-tag v-if="detailPushStatusMeta" :type="detailPushStatusMeta.tagType" size="small">
              {{ detailPushStatusMeta.label }}
            </el-tag>
            <span v-else class="muted-text">-</span>
          </div>
        </div>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="基本信息" name="basic">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="候选人">{{ detail.candidate?.name }}</el-descriptions-item>
              <el-descriptions-item label="邮箱">{{ detail.candidate?.email }}</el-descriptions-item>
              <el-descriptions-item label="手机">{{ detail.candidate?.phone || "-" }}</el-descriptions-item>
              <el-descriptions-item label="投递时间">{{ formatDate(detail.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="detailStatusMeta.tagType">{{ detailStatusMeta.label }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="匹配分">{{ detail.match_score ?? "-" }}</el-descriptions-item>
              <el-descriptions-item label="推送状态">
                <el-tag v-if="detailPushStatusMeta" :type="detailPushStatusMeta.tagType" size="small">
                  {{ detailPushStatusMeta.label }}
                </el-tag>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="决策理由">
                {{ detail.agent_result?.decision_reason || "暂无决策理由" }}
              </el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane label="原始表单" name="raw">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="自我介绍">
                <span style="white-space: pre-wrap">{{ detail.form_data?.self_intro || "(未填写)" }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="期望薪资">
                {{ detail.form_data?.expected_salary || "(未填写)" }}
              </el-descriptions-item>
            </el-descriptions>
            <div class="resume-action">
              <el-button type="primary" @click="downloadResume(detail.id)">
                <el-icon><Download /></el-icon>
                下载原始简历
              </el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="AI 解析" name="parsed">
            <template v-if="detail.parsed_resume && Object.keys(detail.parsed_resume).length">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="姓名">{{ detail.parsed_resume.name || "-" }}</el-descriptions-item>
                <el-descriptions-item label="邮箱">{{ detail.parsed_resume.email || "-" }}</el-descriptions-item>
                <el-descriptions-item label="手机">{{ detail.parsed_resume.phone || "-" }}</el-descriptions-item>
              </el-descriptions>

              <h4 class="section-title">教育背景</h4>
              <div v-if="detail.parsed_resume.education?.length">
                <el-tag
                  v-for="education in detail.parsed_resume.education"
                  :key="education"
                  class="inline-tag"
                >
                  {{ education }}
                </el-tag>
              </div>
              <p v-else class="muted-text">暂无教育背景信息</p>

              <h4 class="section-title">技能列表</h4>
              <div v-if="detail.parsed_resume.skills?.length">
                <el-tag
                  v-for="skill in detail.parsed_resume.skills"
                  :key="skill"
                  type="success"
                  class="inline-tag"
                >
                  {{ skill }}
                </el-tag>
              </div>
              <p v-else class="muted-text">暂无技能信息</p>

              <h4 class="section-title">工作经历</h4>
              <div v-if="detail.parsed_resume.work_experience?.length" class="bullet-list">
                <p v-for="experience in detail.parsed_resume.work_experience" :key="experience">• {{ experience }}</p>
              </div>
              <p v-else class="muted-text">暂无工作经历</p>

              <h4 class="section-title">项目经验</h4>
              <div v-if="detail.parsed_resume.projects?.length" class="bullet-list">
                <p v-for="project in detail.parsed_resume.projects" :key="project">• {{ project }}</p>
              </div>
              <p v-else class="muted-text">暂无项目经验</p>
            </template>
            <p v-else class="centered-muted">该投递尚未经过 AI 解析</p>
          </el-tab-pane>

          <el-tab-pane label="筛选报告" name="report">
            <template v-if="detail.agent_result?.report_markdown">
              <el-row v-if="detail.agent_result.dimension_scores" :gutter="12" class="score-row">
                <el-col :span="6" v-for="(score, dimension) in detail.agent_result.dimension_scores" :key="dimension">
                  <el-card shadow="hover" class="score-card">
                    <div class="score-dimension">{{ dimension }}</div>
                    <div
                      class="score-value"
                      :style="{ color: score >= 70 ? '#67c23a' : score >= 40 ? '#e6a23c' : '#f56c6c' }"
                    >
                      {{ score }}
                    </div>
                  </el-card>
                </el-col>
              </el-row>

              <div v-if="detail.agent_result.matched_keywords?.length" class="report-tags">
                <span class="report-label">命中技能：</span>
                <el-tag
                  v-for="keyword in detail.agent_result.matched_keywords"
                  :key="keyword"
                  type="success"
                  size="small"
                  class="inline-tag"
                >
                  {{ keyword }}
                </el-tag>
              </div>
              <div v-if="detail.agent_result.missing_keywords?.length" class="report-tags">
                <span class="report-label">缺失技能：</span>
                <el-tag
                  v-for="keyword in detail.agent_result.missing_keywords"
                  :key="keyword"
                  type="danger"
                  size="small"
                  class="inline-tag"
                >
                  {{ keyword }}
                </el-tag>
              </div>

              <el-alert
                v-for="highlight in detail.agent_result.highlights"
                :key="highlight.detail"
                :title="highlight.type"
                :description="highlight.detail"
                type="success"
                show-icon
                class="report-alert"
              />
              <el-alert
                v-for="risk in detail.agent_result.risks"
                :key="risk.detail"
                :title="risk.type + (risk.severity ? ' (' + risk.severity + ')' : '')"
                :description="risk.detail"
                type="warning"
                show-icon
                class="report-alert"
              />

              <div class="markdown-report" v-html="renderMarkdown(detail.agent_result.report_markdown)" />
            </template>
            <p v-else class="centered-muted">暂无筛选报告</p>
          </el-tab-pane>
        </el-tabs>

        <div class="dialog-footer-actions">
          <span class="footer-tip">手动覆盖决策：</span>
          <el-button
            size="small"
            type="success"
            :disabled="detail.status === 'passed'"
            :loading="overriding"
            @click="overrideStatus('passed')"
          >
            设为通过
          </el-button>
          <el-button
            size="small"
            type="warning"
            :disabled="detail.status === 'pending_review'"
            :loading="overriding"
            @click="overrideStatus('pending_review')"
          >
            设为待复审
          </el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="detail.status === 'rejected'"
            :loading="overriding"
            @click="overrideStatus('rejected')"
          >
            设为不通过
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  hrBatchRescreen,
  hrDownloadResume,
  hrGetApplicationDetail,
  hrGetApplications,
  hrRescreen,
  hrRescreenSelected,
  hrUpdateAppStatus,
} from "../../api/index.js";
import { buildApplicationListSummary } from "./admin_experience_helpers.js";
import {
  getApplicationStatusMeta,
  getPushStatusMeta,
} from "./application_list_status.js";

const route = useRoute();
const tableRef = ref(null);
const applications = ref([]);
const loading = ref(false);
const searchText = ref("");
const filterStatus = ref("");
const batching = ref(false);
const selectedBatching = ref(false);
const dialogVisible = ref(false);
const detail = ref(null);
const activeTab = ref("basic");
const overriding = ref(false);
const currentPage = ref(1);
const pageSize = 10;
const selectedApplicationIds = ref([]);
const rescreeningId = ref("");

const sortedApplications = computed(() => [...applications.value].sort((left, right) => {
  const leftScore = Number(left.match_score ?? -1);
  const rightScore = Number(right.match_score ?? -1);

  if (rightScore !== leftScore) {
    return rightScore - leftScore;
  }

  return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
}));
const detailStatusMeta = computed(() => getApplicationStatusMeta(detail.value?.status));
const detailPushStatusMeta = computed(() => getPushStatusMeta(detail.value?.push_status));
const listSummary = computed(() =>
  buildApplicationListSummary(applications.value, {
    searchText: searchText.value,
    filterStatus: filterStatus.value,
  })
);
const pagedApps = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return sortedApplications.value.slice(start, start + pageSize);
});
const emptyDescription = computed(() => {
  if (searchText.value.trim() && filterStatus.value) {
    return "当前关键词和状态组合下没有投递记录，请尝试放宽筛选条件。";
  }
  if (searchText.value.trim()) {
    return "没有找到匹配该关键词的投递记录，请检查姓名或邮箱。";
  }
  if (filterStatus.value) {
    return "当前状态下没有投递记录，请切换其他状态查看。";
  }
  return "当前岗位暂无投递记录，发布岗位后可回到这里查看筛选结果。";
});

const fetchApps = async () => {
  loading.value = true;
  try {
    const params = {};
    if (filterStatus.value) {
      params.status = filterStatus.value;
    }
    if (searchText.value.trim()) {
      params.search = searchText.value.trim();
    }
    const res = await hrGetApplications(route.params.id, params);
    applications.value = res.data || [];
    currentPage.value = 1;
    selectedApplicationIds.value = [];
    tableRef.value?.clearSelection?.();
  } finally {
    loading.value = false;
  }
};

onMounted(fetchApps);

watch(currentPage, () => {
  selectedApplicationIds.value = [];
  tableRef.value?.clearSelection?.();
});

const getRowIndex = (index) => (currentPage.value - 1) * pageSize + index + 1;
const getApplicationStatusLabel = (status) => getApplicationStatusMeta(status).label;
const getApplicationStatusTagType = (status) => getApplicationStatusMeta(status).tagType;
const getPushStatusLabel = (status) => getPushStatusMeta(status)?.label || "-";
const getPushStatusTagType = (status) => getPushStatusMeta(status)?.tagType || "info";
const hasPushStatusMeta = (status) => Boolean(getPushStatusMeta(status));

const handleSelectionChange = (rows) => {
  selectedApplicationIds.value = rows.map((row) => row.id);
};

const showDetail = async (row) => {
  activeTab.value = "basic";
  try {
    const res = await hrGetApplicationDetail(row.id);
    detail.value = res.data;
    dialogVisible.value = true;
  } catch (error) {
    ElMessage.error("获取详情失败，请稍后重试");
  }
};

const rescreen = async (appId) => {
  rescreeningId.value = appId;
  try {
    await hrRescreen(appId);
    ElMessage.success("已重新触发该投递的筛选流程");
    await fetchApps();
  } catch (error) {
    const message = error.response?.data?.detail || error.response?.data?.error || "操作失败";
    ElMessage.error(message);
  } finally {
    rescreeningId.value = "";
  }
};

const rescreenSelected = async () => {
  if (!selectedApplicationIds.value.length) {
    ElMessage.warning("请先勾选投递记录");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确认将当前勾选的 ${selectedApplicationIds.value.length} 条投递加入筛选队列吗？`,
      "确认批量筛选",
      {
        confirmButtonText: "加入队列",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
  } catch {
    return;
  }

  selectedBatching.value = true;
  try {
    const res = await hrRescreenSelected(selectedApplicationIds.value);
    const missingCount = res.data.missing_ids?.length || 0;
    const missingText = missingCount ? `，其中 ${missingCount} 条未加入队列` : "";
    ElMessage.success(`已加入 ${res.data.queued_count} 条投递到筛选队列${missingText}`);
    await fetchApps();
  } catch (error) {
    const message = error.response?.data?.detail || error.response?.data?.error || "筛选选中项失败";
    ElMessage.error(message);
  } finally {
    selectedBatching.value = false;
  }
};

const batchRescreen = async () => {
  if (!applications.value.length) {
    ElMessage.warning("当前岗位暂无可筛选的投递记录");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确认将当前岗位下 ${applications.value.length} 条投递全部加入筛选队列吗？`,
      "确认一键筛选",
      {
        confirmButtonText: "全部加入队列",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
  } catch {
    return;
  }

  batching.value = true;
  try {
    const res = await hrBatchRescreen(route.params.id);
    ElMessage.success(`已加入 ${res.data.queued_count} 条投递到筛选队列`);
    await fetchApps();
  } catch (error) {
    const message = error.response?.data?.detail || error.response?.data?.error || "批量筛选失败";
    ElMessage.error(message);
  } finally {
    batching.value = false;
  }
};

const overrideStatus = async (status) => {
  overriding.value = true;
  try {
    await hrUpdateAppStatus(detail.value.id, status);
    ElMessage.success("决策已更新");
    dialogVisible.value = false;
    await fetchApps();
  } catch (error) {
    const message = error.response?.data?.detail || "操作失败";
    ElMessage.error(message);
  } finally {
    overriding.value = false;
  }
};

const getDownloadFilename = (contentDisposition, fallbackName) => {
  if (!contentDisposition) {
    return fallbackName;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const asciiMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i);
  if (asciiMatch?.[1]) {
    return asciiMatch[1];
  }

  return fallbackName;
};

const downloadResume = async (appId) => {
  try {
    const res = await hrDownloadResume(appId);
    const contentDisposition = res.headers["content-disposition"];
    const fallbackName = `resume_${appId}`;
    const filename = getDownloadFilename(contentDisposition, fallbackName);
    const url = URL.createObjectURL(res.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error("简历下载失败，文件可能已被删除");
  }
};

const formatDate = (value) => {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
};

const renderMarkdown = (markdown) => {
  if (!markdown) {
    return "";
  }

  return markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\|(.+)\|\n\|[- |:]+\|\n((?:\|.+\|\n?)*)/gm, (_, header, rows) => {
      const headerHtml = header.split("|").map((cell) => `<th>${cell.trim()}</th>`).join("");
      const rowHtml = rows.trim().split("\n").map((row) =>
        `<tr>${row.split("|").filter((cell) => cell).map((cell) => `<td>${cell.trim()}</td>`).join("")}</tr>`
      ).join("");
      return `<table><thead><tr>${headerHtml}</tr></thead><tbody>${rowHtml}</tbody></table>`;
    })
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)\n(?=<li>)/gs, "$1")
    .replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>")
    .replace(/\n/g, "<br>");
};
</script>

<style scoped>
.application-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.back-button {
  margin-bottom: 12px;
}

.page-title {
  margin: 0;
  color: #12233d;
  font-size: 28px;
  font-weight: 700;
}

.page-subtitle {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.7;
}

.summary-row {
  margin-top: 2px;
}

.summary-card {
  border-radius: 18px;
}

.summary-label {
  color: #6b7280;
  font-size: 13px;
}

.summary-value {
  margin-top: 10px;
  color: #16213e;
  font-size: 30px;
  font-weight: 700;
}

.summary-filter {
  margin-top: 12px;
  color: #16213e;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}

.summary-hint {
  margin-top: 8px;
  color: #8a94a6;
  font-size: 12px;
  line-height: 1.6;
}

.toolbar-card {
  border-radius: 18px;
}

.toolbar-row {
  align-items: center;
}

.toolbar-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  color: #6b7280;
  font-size: 13px;
  flex-wrap: wrap;
}

.candidate-name {
  color: #16213e;
  font-weight: 600;
}

.candidate-time {
  margin-top: 6px;
  color: #8a94a6;
  font-size: 12px;
}

.muted-text {
  color: #8a94a6;
  font-size: 12px;
}

.pagination {
  justify-content: flex-end;
}

.detail-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.detail-overview-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #f8fafc;
}

.detail-overview-label {
  color: #6b7280;
  font-size: 12px;
}

.resume-action {
  margin-top: 16px;
}

.section-title {
  margin: 16px 0 8px;
  color: #16213e;
  font-size: 15px;
}

.inline-tag {
  margin: 0 8px 6px 0;
}

.bullet-list p {
  margin: 4px 0;
  font-size: 13px;
}

.centered-muted {
  padding: 32px 0;
  color: #8a94a6;
  text-align: center;
}

.score-row {
  margin-bottom: 16px;
}

.score-card {
  text-align: center;
}

.score-dimension {
  margin-bottom: 4px;
  color: #8a94a6;
  font-size: 12px;
}

.score-value {
  font-size: 24px;
  font-weight: 700;
}

.report-tags {
  margin-bottom: 12px;
}

.report-label {
  color: #6b7280;
  font-size: 13px;
}

.report-alert {
  margin-bottom: 8px;
}

.dialog-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.footer-tip {
  margin-right: auto;
  color: #8a94a6;
  font-size: 13px;
}

.markdown-report {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  border-radius: 8px;
  background: #f9f9f9;
  font-size: 14px;
  line-height: 1.8;
}

.markdown-report :deep(table) {
  width: 100%;
  margin: 8px 0;
  border-collapse: collapse;
}

.markdown-report :deep(th),
.markdown-report :deep(td) {
  padding: 8px 12px;
  border: 1px solid #ddd;
  text-align: left;
}

.markdown-report :deep(th) {
  background: #f0f0f0;
  font-weight: 600;
}

.markdown-report :deep(pre) {
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  background: #2d2d2d;
  color: #f8f8f2;
}

.markdown-report :deep(code) {
  font-family: "Fira Code", "Consolas", monospace;
  font-size: 13px;
}

.markdown-report :deep(ul) {
  padding-left: 20px;
}

@media (max-width: 991px) {
  .toolbar-actions {
    justify-content: flex-start;
  }

  .detail-overview {
    grid-template-columns: 1fr;
  }
}
</style>
