<template>
  <div class="dashboard-page">
    <div class="hero-panel">
      <div>
        <p class="eyebrow">工作台</p>
        <h2 class="hero-title">招聘进展一览</h2>
        <p class="hero-subtitle">
          通过时间趋势、状态分布和岗位排行快速定位问题岗位与高价值候选人。
        </p>
      </div>
      <div class="hero-actions">
        <el-radio-group v-model="activeDays" size="small" @change="fetchStats">
          <el-radio-button :label="7">近 7 天</el-radio-button>
          <el-radio-button :label="30">近 30 天</el-radio-button>
        </el-radio-group>
        <el-button type="primary" @click="$router.push('/admin/jobs')">管理岗位</el-button>
      </div>
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col :xs="24" :sm="12" :lg="6" v-for="card in summaryCards" :key="card.key">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">{{ card.label }}</div>
          <div class="summary-value">{{ card.value }}</div>
          <div class="summary-hint">{{ card.hint }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="15">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>{{ activeDays }} 天投递趋势</span>
              <span class="header-tip">悬浮可查看单日投递与通过详情</span>
            </div>
          </template>

          <div v-if="trend.length" class="line-chart-wrap">
            <div class="chart-stage" @mouseleave="hideTooltip">
              <svg viewBox="0 0 640 220" class="line-chart">
                <g v-for="grid in chartGrid" :key="grid.y">
                  <line
                    :x1="chartPadding.left"
                    :x2="640 - chartPadding.right"
                    :y1="grid.y"
                    :y2="grid.y"
                    class="grid-line"
                  />
                  <text :x="chartPadding.left - 12" :y="grid.y + 4" class="axis-text value-axis">
                    {{ grid.value }}
                  </text>
                </g>

                <polyline :points="applicationsPoints" class="trend-line applications-line" />
                <polyline :points="passedPoints" class="trend-line passed-line" />

                <g v-for="(item, index) in trend" :key="item.date">
                  <line
                    :x1="getPointX(index)"
                    :x2="getPointX(index)"
                    :y1="chartPadding.top"
                    :y2="220 - chartPadding.bottom"
                    class="hover-column"
                    @mousemove="showTrendTooltip($event, item)"
                  />
                  <circle
                    :cx="getPointX(index)"
                    :cy="getPointY(item.applications)"
                    r="4"
                    class="applications-dot"
                    @mousemove="showTrendTooltip($event, item)"
                  />
                  <circle
                    :cx="getPointX(index)"
                    :cy="getPointY(item.passed)"
                    r="4"
                    class="passed-dot"
                    @mousemove="showTrendTooltip($event, item)"
                  />
                  <text :x="getPointX(index)" :y="210" class="axis-text date-axis">
                    {{ formatTrendDateLabel(item.date, activeDays, index) }}
                  </text>
                </g>
              </svg>

              <div
                v-if="tooltip.visible"
                class="chart-tooltip"
                :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
              >
                <div class="tooltip-title">{{ tooltip.title }}</div>
                <template v-if="tooltip.mode === 'trend' || tooltip.mode === 'top-job'">
                  <div>投递量：{{ tooltip.applications }}</div>
                  <div>通过量：{{ tooltip.passed }}</div>
                </template>
                <template v-else>
                  <div>数量：{{ tooltip.applications }}</div>
                </template>
              </div>
            </div>

            <div class="chart-legend">
              <span><i class="legend-dot applications-dot"></i>投递量</span>
              <span><i class="legend-dot passed-dot"></i>通过量</span>
            </div>
          </div>
          <el-empty v-else :description="`${activeDays} 天内暂无趋势数据`" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="9">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>{{ activeDays }} 天状态分布</span>
              <span class="header-tip">颜色与投递列表状态保持一致</span>
            </div>
          </template>

          <div class="status-bars">
            <div
              v-for="item in statusDistribution"
              :key="item.status"
              class="status-row"
              @mousemove="showStatusTooltip($event, item)"
              @mouseleave="hideTooltip"
            >
              <div class="status-meta">
                <span>{{ item.label }}</span>
                <span>{{ item.value }}</span>
              </div>
              <div class="status-track">
                <div
                  class="status-fill"
                  :class="`status-${item.status}`"
                  :style="{ width: `${getStatusPercent(item.value)}%` }"
                ></div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="ranking-row">
      <el-col :xs="24" :lg="16">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>{{ activeDays }} 天岗位投递量排行</span>
              <span class="header-tip">Top 5 岗位</span>
            </div>
          </template>

          <div v-if="topJobs.length" class="ranking-list">
            <div
              v-for="(job, index) in topJobs"
              :key="job.job_id"
              class="ranking-item"
              @mousemove="showTopJobTooltip($event, job)"
              @mouseleave="hideTooltip"
            >
              <div class="ranking-info">
                <div class="rank-badge">{{ index + 1 }}</div>
                <div>
                  <div class="job-title">{{ job.title }}</div>
                  <div class="job-meta">投递 {{ job.application_count }} · 通过 {{ job.passed_count }}</div>
                </div>
              </div>
              <div class="ranking-bar">
                <div class="ranking-fill" :style="{ width: `${getTopJobPercent(job.application_count)}%` }"></div>
              </div>
            </div>
          </div>
          <el-empty v-else :description="`${activeDays} 天内暂无岗位排行数据`" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>{{ activeDays }} 天岗位通过率</span>
              <span class="header-tip">按当前排行岗位统计</span>
            </div>
          </template>

          <div v-if="topJobs.length" class="pass-rate-list">
            <div v-for="job in topJobs" :key="job.job_id" class="pass-rate-item">
              <div class="pass-rate-meta">
                <span>{{ job.title }}</span>
                <span>{{ job.pass_rate }}%</span>
              </div>
              <el-progress
                :percentage="job.pass_rate"
                :stroke-width="10"
                :show-text="false"
                :color="getPassRateColor(job.pass_rate)"
              />
            </div>
          </div>
          <el-empty v-else :description="`${activeDays} 天内暂无通过率数据`" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { hrDashboardStats } from "../../api/index.js";
import { formatTrendDateLabel } from "./dashboard_chart.js";

const chartPadding = {
  top: 20,
  right: 16,
  bottom: 34,
  left: 38,
};

const activeDays = ref(7);
const stats = reactive({
  total_jobs: 0,
  published_jobs: 0,
  draft_jobs: 0,
  total_applications: 0,
  pending_count: 0,
  processing_count: 0,
  passed_count: 0,
  pending_review_count: 0,
  rejected_count: 0,
});

const trend = ref([]);
const statusDistribution = ref([]);
const topJobs = ref([]);
const tooltip = reactive({
  visible: false,
  mode: "trend",
  title: "",
  applications: 0,
  passed: 0,
  x: 0,
  y: 0,
});

const summaryCards = computed(() => [
  {
    key: "jobs",
    label: "岗位总数",
    value: stats.total_jobs,
    hint: `已发布 ${stats.published_jobs} · 草稿 ${stats.draft_jobs}`,
  },
  {
    key: "applications",
    label: "累计投递",
    value: stats.total_applications,
    hint: `待筛选 ${stats.pending_count} · 筛选中 ${stats.processing_count}`,
  },
  {
    key: "passed",
    label: "已通过",
    value: stats.passed_count,
    hint: `待复审 ${stats.pending_review_count}`,
  },
  {
    key: "rejected",
    label: "未通过",
    value: stats.rejected_count,
    hint: `当前查看近 ${activeDays.value} 天图表数据`,
  },
]);

const distributionTotal = computed(() =>
  statusDistribution.value.reduce((sum, item) => sum + item.value, 0)
);

const maxTrendValue = computed(() => {
  const values = trend.value.flatMap((item) => [item.applications, item.passed]);
  return Math.max(...values, 1);
});

const chartGrid = computed(() => {
  const max = maxTrendValue.value;
  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = Math.round(max * ratio);
    return {
      value,
      y: getPointY(value),
    };
  });
});

const applicationsPoints = computed(() =>
  trend.value.map((item, index) => `${getPointX(index)},${getPointY(item.applications)}`).join(" ")
);

const passedPoints = computed(() =>
  trend.value.map((item, index) => `${getPointX(index)},${getPointY(item.passed)}`).join(" ")
);

const fetchStats = async () => {
  try {
    const res = await hrDashboardStats(activeDays.value);
    Object.assign(stats, res.data);
    trend.value = res.data.trend || [];
    statusDistribution.value = res.data.status_distribution || [];
    topJobs.value = res.data.top_jobs || [];
  } catch (e) {
    console.error(e);
  }
};

const getPointX = (index) => {
  if (trend.value.length <= 1) {
    return chartPadding.left;
  }
  const width = 640 - chartPadding.left - chartPadding.right;
  return chartPadding.left + (width * index) / (trend.value.length - 1);
};

const getPointY = (value) => {
  const height = 220 - chartPadding.top - chartPadding.bottom;
  const ratio = value / maxTrendValue.value;
  return chartPadding.top + height - height * ratio;
};

const getStatusPercent = (value) => {
  if (!distributionTotal.value) {
    return 0;
  }
  return Math.max((value / distributionTotal.value) * 100, value ? 8 : 0);
};

const getTopJobPercent = (value) => {
  const max = Math.max(...topJobs.value.map((item) => item.application_count), 1);
  return (value / max) * 100;
};

const getPassRateColor = (passRate) => {
  if (passRate >= 70) {
    return "#1fa971";
  }
  if (passRate >= 40) {
    return "#f59e0b";
  }
  return "#ef4444";
};

const showTooltip = (event, payload) => {
  tooltip.visible = true;
  tooltip.mode = payload.mode;
  tooltip.title = payload.title;
  tooltip.applications = payload.applications;
  tooltip.passed = payload.passed;
  tooltip.x = event.clientX + 16;
  tooltip.y = event.clientY + 12;
};

const showTrendTooltip = (event, item) => {
  showTooltip(event, {
    mode: "trend",
    title: item.date,
    applications: item.applications,
    passed: item.passed,
  });
};

const showStatusTooltip = (event, item) => {
  showTooltip(event, {
    mode: "status",
    title: item.label,
    applications: item.value,
    passed: 0,
  });
};

const showTopJobTooltip = (event, job) => {
  showTooltip(event, {
    mode: "top-job",
    title: job.title,
    applications: job.application_count,
    passed: job.passed_count,
  });
};

const hideTooltip = () => {
  tooltip.visible = false;
};

onMounted(fetchStats);
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  padding: 22px 24px;
  border-radius: 20px;
  background: linear-gradient(135deg, #0d2238 0%, #1d4f7a 55%, #7ec8e3 100%);
  color: #fff;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.85;
}

.hero-title {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
}

.hero-subtitle {
  margin: 10px 0 0;
  max-width: 760px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.92);
}

.summary-card,
.chart-card {
  border-radius: 18px;
}

.summary-label {
  color: #6b7280;
  font-size: 13px;
}

.summary-value {
  margin-top: 10px;
  font-size: 32px;
  font-weight: 700;
  color: #16213e;
}

.summary-hint {
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

.header-tip {
  color: #8a94a6;
  font-size: 12px;
}

.line-chart-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chart-stage {
  position: relative;
}

.line-chart {
  width: 100%;
  height: auto;
}

.grid-line {
  stroke: #e5e7eb;
  stroke-dasharray: 4 4;
}

.hover-column {
  stroke: transparent;
  stroke-width: 22;
  cursor: pointer;
}

.trend-line {
  fill: none;
  stroke-width: 3;
}

.applications-line {
  stroke: #2563eb;
}

.passed-line {
  stroke: #16a34a;
}

.applications-dot {
  fill: #2563eb;
}

.passed-dot {
  fill: #16a34a;
}

.axis-text {
  fill: #8a94a6;
  font-size: 11px;
}

.date-axis {
  text-anchor: middle;
}

.value-axis {
  text-anchor: end;
}

.chart-tooltip {
  position: fixed;
  z-index: 20;
  min-width: 140px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.92);
  color: #fff;
  font-size: 12px;
  line-height: 1.6;
  pointer-events: none;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.24);
}

.tooltip-title {
  margin-bottom: 4px;
  font-weight: 700;
}

.chart-legend {
  display: flex;
  gap: 20px;
  color: #4b5563;
  font-size: 13px;
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 6px;
  border-radius: 50%;
}

.status-bars,
.pass-rate-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.status-row,
.pass-rate-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-meta,
.pass-rate-meta {
  display: flex;
  justify-content: space-between;
  color: #4b5563;
  font-size: 13px;
}

.status-track,
.ranking-bar {
  height: 10px;
  border-radius: 999px;
  background: #edf2f7;
  overflow: hidden;
}

.status-fill,
.ranking-fill {
  height: 100%;
  border-radius: 999px;
}

.status-pending {
  background: #94a3b8;
}

.status-processing {
  background: #f59e0b;
}

.status-passed {
  background: #16a34a;
}

.status-pending_review {
  background: #2563eb;
}

.status-rejected {
  background: #ef4444;
}

.ranking-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ranking-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ranking-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rank-badge {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #102542;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.job-title {
  font-weight: 600;
  color: #1f2937;
}

.job-meta {
  margin-top: 4px;
  color: #8a94a6;
  font-size: 12px;
}

.ranking-fill {
  background: linear-gradient(90deg, #0f766e 0%, #38bdf8 100%);
}

@media (max-width: 991px) {
  .hero-panel {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero-actions {
    width: 100%;
    justify-content: space-between;
    flex-wrap: wrap;
  }
}
</style>
