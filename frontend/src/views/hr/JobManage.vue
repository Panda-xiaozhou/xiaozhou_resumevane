<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
      <h2 style="margin: 0">岗位管理</h2>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon> 新建岗位
      </el-button>
    </div>

    <el-table :data="jobs" style="width: 100%" v-loading="loading" empty-text="暂无岗位">
      <el-table-column type="index" label="序号" width="70" />
      <el-table-column prop="title" label="岗位名称" />
      <el-table-column prop="department" label="部门" width="120" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'published'" type="success">已发布</el-tag>
          <el-tag v-else-if="row.status === 'draft'" type="info">草稿</el-tag>
          <el-tag v-else type="danger">已关闭</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="技能关键词" width="250">
        <template #default="{ row }">
          <el-tag v-for="kw in row.jd_keywords" :key="kw" size="small" style="margin-right: 4px">{{ kw }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/admin/jobs/${row.id}`)">查看投递</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status === 'published'" size="small" type="warning" @click="updateStatus(row.id, 'closed')">关闭</el-button>
          <el-button v-else size="small" type="success" @click="updateStatus(row.id, 'published')">发布</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建 / 编辑对话框 -->
    <el-dialog v-model="showDialog" :title="editingJob ? '编辑岗位' : '新建岗位'" width="640px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="岗位名称">
          <el-input v-model="form.title" placeholder="如：前端开发工程师" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.department" placeholder="如：技术部" />
        </el-form-item>
        <el-form-item label="JD 描述">
          <el-input v-model="form.jd_text" type="textarea" :rows="8" placeholder="请输入岗位职责和要求..." />
        </el-form-item>
        <el-form-item label="技能关键词">
          <el-input v-model="form.jd_keywords" placeholder="多个关键词用逗号分隔，如：Python,FastAPI,React" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button v-if="editingJob" type="danger" @click="deleteJob" :loading="deleting" style="margin-right: auto">删除岗位</el-button>
        <el-button type="primary" @click="submitJob" :loading="submitting">
          {{ editingJob ? '保存修改' : '创建并发布' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { hrListJobs, hrCreateJob, hrUpdateJob, hrDeleteJob, hrUpdateJobStatus } from "../../api/index.js";

const jobs = ref([]);
const loading = ref(false);
const showDialog = ref(false);
const submitting = ref(false);
const deleting = ref(false);
const editingJob = ref(null);

const form = reactive({
  title: "",
  department: "",
  jd_text: "",
  jd_keywords: "",
});

const userId = localStorage.getItem("hr_user_id");

const fetchJobs = async () => {
  loading.value = true;
  try {
    const res = await hrListJobs(userId);
    jobs.value = res.data || [];
  } finally {
    loading.value = false;
  }
};

onMounted(fetchJobs);

const openCreate = () => {
  editingJob.value = null;
  form.title = "";
  form.department = "";
  form.jd_text = "";
  form.jd_keywords = "";
  showDialog.value = true;
};

const openEdit = (job) => {
  editingJob.value = job;
  form.title = job.title;
  form.department = job.department || "";
  form.jd_text = job.jd_text || "";
  form.jd_keywords = (job.jd_keywords || []).join(", ");
  showDialog.value = true;
};

const submitJob = async () => {
  submitting.value = true;
  try {
    if (editingJob.value) {
      // 编辑已有岗位
      const fd = new FormData();
      fd.append("title", form.title);
      fd.append("department", form.department);
      fd.append("jd_text", form.jd_text);
      fd.append("jd_keywords", form.jd_keywords);
      await hrUpdateJob(editingJob.value.id, fd);
      ElMessage.success("岗位已更新");
    } else {
      // 新建岗位
      const fd = new FormData();
      fd.append("hr_user_id", userId);
      fd.append("title", form.title);
      fd.append("department", form.department);
      fd.append("jd_text", form.jd_text);
      fd.append("jd_keywords", form.jd_keywords);
      await hrCreateJob(fd);
      ElMessage.success("岗位已发布");
    }
    showDialog.value = false;
    await fetchJobs();
  } catch (e) {
    ElMessage.error("操作失败");
  } finally {
    submitting.value = false;
  }
};

const deleteJob = async () => {
  try {
    await ElMessageBox.confirm("确定删除该岗位？已收到的投递记录不会受影响。", "确认删除", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  deleting.value = true;
  try {
    await hrDeleteJob(editingJob.value.id);
    ElMessage.success("岗位已删除");
    showDialog.value = false;
    await fetchJobs();
  } catch (e) {
    ElMessage.error("操作失败");
  } finally {
    deleting.value = false;
  }
};

const updateStatus = async (jobId, status) => {
  try {
    await hrUpdateJobStatus(jobId, status);
    ElMessage.success("状态已更新");
    await fetchJobs();
  } catch (e) {
    ElMessage.error("操作失败");
  }
};

const formatDate = (d) => {
  if (!d) return "-";
  return new Date(d).toLocaleString("zh-CN", { hour12: false });
};
</script>
