# ResumeVane

> 招聘简历智能筛选多 Agent 系统 — 让 AI Agent 帮你从海量简历中找到最佳候选人

## 系统架构

```
候选人投递简历 → Agent 自动筛选（6 Agent 流水线） → 通过 → 飞书推送HR部门
                                   ↓
                            HR Web 后台看板复审
```

### 6 个 Agent 角色

| Agent | 职责 |
|-------|------|
| 调度 Agent | 任务初始化、文件预处理、路由分发 |
| 解析 Agent | PDF/Word 简历 → 结构化 JSON |
| 匹配 Agent | 简历 vs JD 多维打分 |
| 分析 Agent | 亮点/风险识别 |
| 报告 Agent | 汇总排序 + 生成简报 |
| 审批 Agent | 决策 + 飞书推送 |

## 技术栈

- **LLM**: DeepSeek（chat API + tool_use）
- **Agent 编排**: LangGraph
- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **向量数据库**: Chroma
- **前端**: Vue 3 + Element Plus + Vite
- **飞书**: lark-oapi SDK
- **部署**: Docker Compose

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 DeepSeek API Key 和飞书应用凭证
```

### 2. Docker Compose 一键启动

```bash
docker-compose up -d
```

### 3. 手动启动（开发模式）

```bash
# 后端
cd backend
pip install -r ../requirements.txt
uvicorn backend.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

### 4. 访问

- 候选人门户: http://localhost:3000
- HR 后台: http://localhost:3000/admin
- API 文档: http://localhost:8000/docs

## 项目结构

```
resumevane/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── models/              # 数据库模型
│   ├── api/                 # API 路由
│   ├── agents/              # LangGraph Agent 核心
│   │   ├── graph.py         # 状态图定义
│   │   ├── state.py         # AgentState
│   │   ├── nodes/           # 6 个 Agent 节点
│   │   └── tools/           # 工具注册
│   ├── services/            # 业务服务
│   └── utils/               # 工具函数
├── frontend/
│   ├── src/views/hr/        # HR 后台页面
│   └── src/views/candidate/ # 候选人门户页面
├── docker-compose.yml
└── requirements.txt
```

## 评测指标

| 指标 | 目标 |
|------|------|
| 简历解析准确率 | ≥ 90% |
| 匹配排序 Precision@5 | ≥ 80% |
| 推荐决策一致性 | ≥ 75% |
| 飞书推送成功率 | ≥ 95% |
| 单份简历 Token 成本 | ≤ 5K tokens |

## License

MIT
