import { createRouter, createWebHistory } from "vue-router";

const routes = [
  // 候选人门户
  {
    path: "/",
    name: "home",
    component: () => import("../views/candidate/JobList.vue"),
  },
  {
    path: "/jobs/:id",
    name: "job-detail",
    component: () => import("../views/candidate/JobDetail.vue"),
  },
  {
    path: "/apply/:id",
    name: "apply",
    component: () => import("../views/candidate/ApplyForm.vue"),
  },
  {
    path: "/status",
    name: "application-status",
    component: () => import("../views/candidate/StatusCheck.vue"),
  },
  // HR 后台
  {
    path: "/admin",
    name: "admin-login",
    component: () => import("../views/hr/Login.vue"),
  },
  {
    path: "/admin",
    component: () => import("../views/hr/HrLayout.vue"),
    children: [
      {
        path: "dashboard",
        name: "admin-dashboard",
        component: () => import("../views/hr/Dashboard.vue"),
      },
      {
        path: "jobs",
        name: "admin-jobs",
        component: () => import("../views/hr/JobManage.vue"),
      },
      {
        path: "vectordb",
        name: "admin-vectordb",
        component: () => import("../views/hr/VectorDbManage.vue"),
      },
      {
        path: "jobs/:id",
        name: "admin-job-applications",
        component: () => import("../views/hr/ApplicationList.vue"),
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 路由守卫——未登录自动跳转登录页
router.beforeEach((to) => {
  if (to.name === "admin-login") {
    // 已登录则跳过登录页
    if (localStorage.getItem("hr_token")) {
      return { name: "admin-dashboard" };
    }
  } else if (to.path.startsWith("/admin")) {
    // 管理页面需验证 token
    if (!localStorage.getItem("hr_token")) {
      return { name: "admin-login" };
    }
  }
});

export default router;
