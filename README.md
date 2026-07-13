# ResumeVane

[![CI](https://github.com/Panda-xiaozhou/xiaozhou_resumevane/actions/workflows/ci.yml/badge.svg)](https://github.com/Panda-xiaozhou/xiaozhou_resumevane/actions/workflows/ci.yml)

> ResumeVane 是一个面向招聘场景的智能简历筛选系统。它用 FastAPI、Vue 3、LangGraph 和 DeepSeek 组成一条可落地的多 Agent 筛选流水线，把“岗位发布、候选人投递、简历解析、JD 匹配、风险分析、报告生成、飞书推送、HR 复审”串成一个完整闭环。

这个项目的目标不是只做一个聊天 Demo，而是模拟真实 HR 团队的工作流：候选人从公开门户投递简历，系统自动读取 PDF/Word 简历并结合岗位 JD 做多维度评估，HR 在后台看板中查看筛选结果、手动复审或批量推送优质候选人到飞书群。

## 项目亮点

- **端到端招聘闭环**：覆盖候选人岗位浏览、在线投递、HR 岗位管理、投递列表、详情报告、状态流转和飞书通知。
- **6 节点 Agent 流水线**：用 LangGraph 编排调度、解析、匹配、分析、报告、审批节点，每个节点职责清晰，便于扩展和调试。
- **结构化筛选结果**：输出匹配分数、维度得分、命中技能、缺失技能、亮点、风险、推荐结论和 Markdown 摘要报告。
- **语义匹配能力**：支持 JD 文本、岗位关键词和标题向量化，结合 BGE-M3 类 OpenAI 兼容 Embedding 接口做语义检索与技能匹配。
- **HR 可运营后台**：提供岗位管理、数据看板、投递复审、简历下载、重新筛选、批量推送和向量库管理入口。
- **飞书集成**：筛选结果可生成飞书消息卡片，并支持将候选人简历文件发送到指定群聊，方便团队协同评审。
- **工程化验证**：包含 GitHub Actions CI、后端测试、前端构建和 Docker 镜像构建验证，适合作为 Agent 项目作品集展示。

## 适用场景

1. **招聘效率提升**：HR 面对大量简历时，先由 Agent 做初筛和报告摘要，再人工复核关键候选人。
2. **Agent 工程实践展示**：展示 LLM 调用、LangGraph 状态流、工具函数、结构化输出、失败降级和外部系统推送。
3. **面试项目讲解**：可以从业务问题、架构设计、Agent 节点、数据模型、前后端联动、CI/CD 和部署方案多个角度展开。
4. **企业内部原型**：可作为招聘自动化、内部人才库、岗位候选人推荐系统的 v1 原型继续扩展。

## 系统流程

```text
HR 创建岗位/JD
      ↓
岗位发布到候选人门户
      ↓
候选人填写信息并上传 PDF/Word 简历
      ↓
后端保存投递记录和简历文件
      ↓
HR 在后台触发筛选或重新筛选
      ↓
LangGraph 多 Agent 流水线执行
      ↓
结构化结果写入数据库并展示在 HR 后台
      ↓
通过/待定候选人可推送到飞书群，HR 团队继续复审
```

## 6 个 Agent 节点

| Agent 节点 | 主要职责 | 关键输出 |
| --- | --- | --- |
| 调度 Agent | 初始化任务、检查输入、准备简历文件和岗位上下文 | 标准化的 AgentState |
| 解析 Agent | 从 PDF/Word 简历中提取候选人基本信息、教育经历、工作经历、技能和项目经历 | `parsed_resume` |
| 匹配 Agent | 将候选人简历与岗位 JD 做多维度评分，结合关键词和语义技能匹配 | `match_score`、`dimension_scores`、命中/缺失技能 |
| 分析 Agent | 识别候选人亮点、潜在风险和综合风险标记 | `highlights`、`risks`、`overall_flag` |
| 报告 Agent | 汇总前序结果，生成 HR 可读的 Markdown 筛选报告 | `report_markdown` |
| 审批 Agent | 根据阈值和风险标记给出推荐、待定或不推荐结论 | `recommend`、`decision_reason` |

当前流水线以稳定性优先，按 `orchestrator -> parser -> matcher -> analyzer -> reporter -> approver` 顺序执行。后续如果要恢复并行，需要先拆分共享状态或为对应字段定义安全 reducer，避免并发写入冲突。

## 功能模块

### 候选人门户

- 浏览已发布岗位列表。
- 查看岗位详情和 JD 完整描述。
- 在线填写姓名、邮箱、手机号、自我介绍、期望薪资等信息。
- 上传 PDF、DOC 或 DOCX 简历文件。
- 按邮箱查询自己的投递历史和筛选状态。

### HR 后台

- HR 注册、登录和 JWT 鉴权。
- 创建、编辑、发布、关闭和删除岗位。
- 查看仪表盘统计：岗位数量、投递数量、处理中数量、通过数量、趋势数据等。
- 查看某个岗位下的投递列表和筛选状态。
- 查看候选人详情、Agent 报告、失败原因和飞书推送结果。
- 手动触发重新筛选、更新投递状态、下载原始简历。
- 批量删除投递或批量推送候选人到飞书。
- 管理岗位向量：嵌入、删除、统计和相似岗位检索。

### 飞书推送

- 通过飞书开放平台应用凭证获取访问令牌。
- 将候选人筛选摘要构造成消息卡片。
- 在卡片中展示岗位、候选人、匹配分、推荐结论、亮点、风险和详情链接。
- 支持上传本地简历文件并发送到目标群聊。
- 将飞书接口失败阶段、错误码、错误信息和 log_id 记录为 HR 可读的失败原因。

### 向量和语义匹配

- 使用 PostgreSQL + pgvector 存储岗位向量。
- 支持 JD 全文、JD 关键词和岗位标题三类向量。
- 默认 Embedding 模型为 `BAAI/bge-m3`，通过 OpenAI 兼容接口调用。
- 可配置语义技能命中阈值 `SEMANTIC_MATCH_THRESHOLD`。
- ChromaDB 保留为备用向量数据库服务，当前主流程以 pgvector 为主。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vue Router、Element Plus、Vite、Axios |
| 后端 | FastAPI、SQLAlchemy、Pydantic、Uvicorn |
| Agent 编排 | LangGraph、DeepSeek Chat API、结构化 JSON 解析 |
| 数据库 | PostgreSQL 16、pgvector、SQLAlchemy ORM |
| 向量化 | BGE-M3 / OpenAI 兼容 Embedding API |
| 队列和缓存 | Redis、ARQ Worker |
| 文件处理 | PyPDF2、python-docx、python-multipart、aiofiles |
| 飞书集成 | lark-oapi、httpx |
| 工程化 | Docker Compose、GitHub Actions、pytest、ruff、npm build |

## 快速开始

### 1. 准备环境

建议本地安装：

- Python 3.12+
- Node.js 20+
- Docker Desktop（推荐，用于 PostgreSQL、Redis、Chroma 和容器化后端）
- Git LFS（仓库中包含演示视频时需要）

如果克隆后演示视频没有拉取下来，可以运行：

```bash
git lfs pull
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`，至少填写：

```dotenv
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
JWT_SECRET_KEY=your-jwt-secret
```

如需飞书推送，再填写：

```dotenv
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_CHAT_ID=oc_xxxxxxxxxxxx
FRONTEND_BASE_URL=http://localhost:3000
```

如需语义向量匹配，再填写或确认：

```dotenv
EMBEDDING_API_KEY=sk-your-embedding-api-key
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
SEMANTIC_MATCH_THRESHOLD=0.7
```

> `.env` 包含密钥，已被 `.gitignore` 排除，请不要提交真实凭证。

### 3. Docker Compose 启动

```bash
docker-compose up -d
```

该命令会启动：

- PostgreSQL + pgvector：`localhost:5432`
- Redis：`localhost:6379`
- ChromaDB：`localhost:8001`
- FastAPI 后端：`localhost:8000`
- ARQ Worker：后台任务处理

查看日志：

```bash
docker-compose logs -f backend
docker-compose logs -f worker
```

停止服务：

```bash
docker-compose down
```

### 4. 本地开发模式

如果只想开发前后端，可以用 Docker 只起数据库和 Redis，再在宿主机运行应用。

后端：

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Worker：

```bash
arq backend.services.task_queue.WorkerSettings --watch backend
```

前端：

```bash
cd frontend
npm install
npm run dev
```

### 5. 访问入口

- 候选人门户：`http://localhost:3000`
- 候选人状态查询：`http://localhost:3000/status`
- HR 后台登录：`http://localhost:3000/admin`
- API 文档：`http://localhost:8000/docs`

## 常用 API

| 模块 | 方法和路径 | 说明 |
| --- | --- | --- |
| 公开岗位 | `GET /api/jobs/` | 查询所有已发布岗位 |
| 公开岗位 | `GET /api/jobs/{job_id}` | 查询岗位详情 |
| 候选人 | `POST /api/candidate/apply` | 提交投递和简历文件 |
| 候选人 | `GET /api/candidate/applications` | 按邮箱查询投递记录 |
| HR 认证 | `POST /api/hr/register` | 注册 HR 用户 |
| HR 认证 | `POST /api/hr/login` | 登录并获取 JWT |
| HR 岗位 | `GET /api/hr/jobs` | 查询当前 HR 的岗位 |
| HR 岗位 | `POST /api/hr/jobs` | 创建岗位 |
| HR 投递 | `GET /api/hr/applications` | 查询投递列表 |
| HR 投递 | `GET /api/hr/applications/{application_id}` | 查询投递详情和 Agent 报告 |
| HR 筛选 | `POST /api/hr/applications/{application_id}/rescreen` | 重新运行 Agent 流水线 |
| HR 飞书 | `POST /api/hr/applications/actions/push-selected` | 批量推送候选人到飞书 |
| 向量库 | `GET /api/hr/vectordb/stats` | 查看岗位向量统计 |

具体请求体和响应结构以 FastAPI 自动生成的 `/docs` 为准。

## 项目结构

```text
resumevane/
├── backend/
│   ├── main.py                    # FastAPI 应用入口、路由注册、生命周期初始化
│   ├── config.py                  # 环境变量和运行参数
│   ├── api/                       # HTTP API 路由
│   │   ├── candidate.py           # 候选人投递和查询
│   │   ├── hr.py                  # HR 后台、筛选、飞书、向量库接口
│   │   └── jobs.py                # 公开岗位浏览接口
│   ├── agents/
│   │   ├── graph.py               # LangGraph 状态图定义
│   │   ├── state.py               # AgentState 共享状态
│   │   └── nodes/                 # 6 个 Agent 节点
│   ├── models/                    # SQLAlchemy 数据模型
│   ├── schemas/                   # Pydantic 请求/响应模型
│   ├── services/                  # 业务服务、飞书、向量、队列、鉴权
│   ├── tests/                     # 后端自动化测试
│   └── utils/                     # LLM、Embedding、文件解析、日志等工具
├── frontend/
│   ├── src/views/candidate/       # 候选人门户页面
│   ├── src/views/hr/              # HR 后台页面
│   ├── src/router/                # Vue Router 和鉴权跳转
│   └── src/api/                   # 前端 API 封装
├── 项目演示视频/                  # 演示视频（Git LFS 管理）
├── .github/workflows/ci.yml       # GitHub Actions CI
├── docker-compose.yml             # 本地基础设施和后端编排
├── Dockerfile                     # FastAPI 后端镜像
├── requirements.txt               # Python 依赖
└── README.md
```

## 数据模型概览

| 模型 | 说明 |
| --- | --- |
| `HrUser` | HR 用户账号、密码哈希、展示名 |
| `Candidate` | 候选人基础信息，按邮箱复用候选人记录 |
| `Job` | 岗位信息、JD、关键词、状态和所属 HR |
| `Application` | 一次候选人投递，关联岗位、简历文件、状态和匹配分 |
| `AgentResult` | Agent 流水线输出，包括报告、分数、结论和原始结构化数据 |
| `JobEmbedding` | 岗位向量，支持 JD 全文、关键词和标题三类 embedding |

## 筛选状态说明

| 状态 | 含义 |
| --- | --- |
| `pending` | 已投递，等待筛选 |
| `processing` | Agent 正在筛选 |
| `passed` | 达到自动推荐条件，可推送飞书 |
| `pending_review` | 需要 HR 人工复审 |
| `screening_failed` | Agent 流水线执行失败，需要查看失败原因或重新筛选 |
| `rejected` | 未达到推荐标准 |

默认审批阈值：

- `PASS_THRESHOLD=75`：匹配度不低于该值且综合评级为 green 时自动推荐。
- `REVIEW_THRESHOLD=60`：匹配度不低于该值且综合评级不是 red 时进入待复审。
- 低于复审阈值时归为不推荐。

## 测试与验证

后端检查：

```bash
python -m ruff check backend/ --ignore E501
pytest backend/tests/ -v --cov=backend --cov-report=term-missing
python -m compileall backend -q
```

前端构建：

```bash
cd frontend
npm run build
```

Docker 构建：

```bash
docker build -t resumevane:ci .
```

GitHub Actions 当前会在 push 和 pull request 时运行：

- 后端依赖安装、ruff、pytest + coverage。
- 前端 `npm ci` 和 `npm run build`。
- Docker 镜像构建。

## 安全和配置注意事项

- 不要提交 `.env`、真实 API Key、飞书 App Secret 或数据库密码。
- `uploads/` 和临时日志文件属于本地运行数据，不应纳入版本控制。
- Docker 镜像不复制 `.env`，生产环境请通过容器环境变量、CI/CD Secret 或云平台 Secret 注入配置。
- HR 后台使用 JWT Bearer Token 鉴权，生产环境务必设置高强度 `JWT_SECRET_KEY`。
- 飞书推送属于可选能力，不配置飞书凭证时应把系统作为本地筛选和后台复审工具使用。

## 演示视频

仓库包含项目演示视频：

```text
项目演示视频/基于飞书通知的简历筛选智能体演示视频.mp4
```

该文件超过 GitHub 普通文件大小限制，已通过 Git LFS 管理。克隆仓库后如需观看视频，请确保本机安装 Git LFS 并运行 `git lfs pull`。

## 后续可扩展方向

- 将投递后自动筛选切到稳定的后台任务队列，并完善任务重试和幂等控制。
- 为 Agent 节点增加更细粒度的评测集，跟踪解析准确率、匹配排序质量和推荐一致性。
- 支持多 HR 团队、多租户隔离和更细粒度的岗位权限。
- 增加人工反馈闭环，把 HR 的通过/拒绝结果回流到后续匹配策略中。
- 增加更完整的生产部署方案，如 HTTPS、对象存储、日志采集、监控告警和数据库迁移。

## License

MIT
