<template>
  <el-container style="min-height: 100vh; background: #f5f7fa">
    <el-header style="background: #1a1a2e; display: flex; align-items: center">
      <div style="color: #fff; font-size: 22px; font-weight: 700; cursor: pointer" @click="$router.push('/')">
        <el-icon><MagicStick /></el-icon> ResumeVane
      </div>
    </el-header>

    <el-main style="max-width: 640px; margin: 0 auto; width: 100%">
      <el-card>
        <template #header>
          <span style="font-size: 18px; font-weight: 600">投递简历</span>
        </template>

        <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
          <el-form-item label="姓名" prop="name">
            <el-input v-model="form.name" placeholder="请输入姓名" />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="form.email" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="form.phone" placeholder="请输入手机号（选填）" />
          </el-form-item>
          <el-form-item label="自我介绍">
            <el-input v-model="form.self_intro" type="textarea" :rows="4" placeholder="简要介绍自己（选填）" />
          </el-form-item>
          <el-form-item label="期望薪资">
            <el-input v-model="form.expected_salary" placeholder="如：15K-20K（选填）" />
          </el-form-item>
          <el-form-item label="简历附件" prop="resume">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              :on-change="onFileChange"
              accept=".pdf,.doc,.docx"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon> 上传简历
              </el-button>
              <template #tip>
                <div style="color: #999; font-size: 12px">支持 PDF、Word 格式，不超过 10MB</div>
              </template>
            </el-upload>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" @click="onSubmit" :loading="submitting">
              提交投递
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, reactive } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { submitApplication } from "../../api/index.js";

const route = useRoute();
const router = useRouter();
const submitting = ref(false);
const uploadFile = ref(null);
const maxResumeSize = 10 * 1024 * 1024;

const form = reactive({
  name: "",
  email: "",
  phone: "",
  self_intro: "",
  expected_salary: "",
});

const rules = {
  name: [{ required: true, message: "请输入姓名", trigger: "blur" }],
  email: [
    { required: true, message: "请输入邮箱", trigger: "blur" },
    { type: "email", message: "请输入有效邮箱", trigger: "blur" },
  ],
};

const onFileChange = (file) => {
  if (file.raw?.size > maxResumeSize) {
    uploadFile.value = null;
    ElMessage.warning("简历文件不能超过 10MB");
    return;
  }
  uploadFile.value = file.raw;
};

const onSubmit = async () => {
  if (!uploadFile.value) {
    ElMessage.warning("请上传简历");
    return;
  }
  submitting.value = true;
  try {
    const fd = new FormData();
    fd.append("name", form.name);
    fd.append("email", form.email);
    fd.append("phone", form.phone);
    fd.append("job_id", route.params.id);
    fd.append("self_intro", form.self_intro);
    fd.append("expected_salary", form.expected_salary);
    fd.append("resume", uploadFile.value);

    await submitApplication(fd);
    ElMessage.success("投递成功！简历已进入智能筛选队列");
    router.push({ path: "/status", query: { email: form.email } });
  } catch (e) {
    ElMessage.error("投递失败，请稍后重试");
  } finally {
    submitting.value = false;
  }
};
</script>
