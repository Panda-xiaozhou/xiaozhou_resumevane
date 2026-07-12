import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

const publicHrPaths = new Set(["/hr/login", "/hr/register"]);

api.interceptors.request.use((config) => {
  const url = config.url || "";
  if (!url.startsWith("/hr") || publicHrPaths.has(url)) {
    return config;
  }

  const token = localStorage.getItem("hr_token");
  if (!token) {
    return config;
  }

  config.headers = config.headers || {};
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── 岗位 ──
export const getPublishedJobs = () => api.get("/jobs/");
export const getJobDetail = (id) => api.get(`/jobs/${id}`);

// ── 候选人 ──
export const submitApplication = (formData) =>
  api.post("/candidate/apply", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
export const getApplicationStatus = (email) =>
  api.get("/candidate/applications", { params: { email } });

// ── HR 认证 ──
export const hrLogin = (username, password) =>
  api.post("/hr/login", { username, password }, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    transformRequest: [(data) => new URLSearchParams(data).toString()],
  });

// ── HR 岗位管理 ──
export const hrCreateJob = (formData) =>
  api.post("/hr/jobs", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
export const hrListJobs = (hrUserId) =>
  api.get("/hr/jobs", { params: { hr_user_id: hrUserId } });
export const hrUpdateJob = (jobId, formData) =>
  api.put(`/hr/jobs/${jobId}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
export const hrDeleteJob = (jobId) =>
  api.delete(`/hr/jobs/${jobId}`);
export const hrUpdateJobStatus = (jobId, status) =>
  api.put(`/hr/jobs/${jobId}/status`, null, { params: { status } });
export const hrDashboardStats = (days = 7) =>
  api.get("/hr/dashboard/stats", { params: { days } });
export const hrEmbedJob = (jobId) =>
  api.post(`/hr/jobs/${jobId}/embed`);
export const hrDeleteJobEmbedding = (jobId) =>
  api.delete(`/hr/jobs/${jobId}/embed`);
export const hrEmbedAllJobs = () =>
  api.post("/hr/jobs/embed-all");
export const hrReembedAllJobs = () =>
  api.post("/hr/jobs/reembed-all");
export const hrGetVectorStats = () =>
  api.get("/hr/vectordb/stats");
export const hrGetEmbeddedJobs = (params = {}) =>
  api.get("/hr/vectordb/jobs", { params });
export const hrGetUnembeddedJobs = (params = {}) =>
  api.get("/hr/vectordb/unembedded-jobs", { params });
export const hrGetJobEmbeddingDetail = (jobId) =>
  api.get(`/hr/jobs/${jobId}/embed`);
export const hrGetSimilarJobs = (jobId, params = {}) =>
  api.get(`/hr/jobs/${jobId}/similar-jobs`, { params });

// ── HR 投递管理 ──
export const hrGetApplications = (jobId, params = {}) =>
  api.get("/hr/applications", { params: { job_id: jobId, ...params } });
export const hrGetApplicationDetail = (appId) =>
  api.get(`/hr/applications/${appId}`);
export const hrUpdateAppStatus = (appId, status) =>
  api.put(`/hr/applications/${appId}/status`, null, { params: { status } });
export const hrDownloadResume = (appId) =>
  api.get(`/hr/applications/${appId}/resume`, { responseType: "blob" });
export const hrRescreen = (appId) =>
  api.post(`/hr/applications/${appId}/rescreen`);
export const hrRescreenSelected = (applicationIds) =>
  api.post("/hr/applications/rescreen-selected", applicationIds);
export const hrBatchRescreen = (jobId) =>
  api.post(`/hr/jobs/${jobId}/rescreen-all`);
