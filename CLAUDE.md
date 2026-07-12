# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 后端开发（热重载，端口 8000）
uvicorn backend.main:app --reload --port 8000

# 前端开发（端口 3000，API 代理到 :8000）
cd frontend && npm run dev

# 前端构建
cd frontend && npm run build

# Docker Compose 全栈启动（PostgreSQL + Chroma + FastAPI）
docker-compose up -d

# 查看后端日志
docker-compose logs -f backend

# 安装 Python 依赖
pip install -r requirements.txt
```

## 核心架构

### Agent 流水线（6 节点 LangGraph）

```
orchestrator → parser → matcher ─┬─→ reporter → approver → END
                      → analyzer ─┘
```

- **orchestrator**：入口，校验任务完整性（JD、简历路径）
- **parser**：PDF/Word → 纯文本 → DeepSeek 结构化提取（JSON）
- **matcher**：简历 vs JD 四维度打分（hard_skill/education/experience/project），权重可配
- **analyzer**：亮点/风险检测 → 综合评级 green/yellow/red
- **reporter**：汇总 matcher 定量分 + analyzer 定性分析 → Markdown 报告（含降级方案）
- **approver**：规则决策（不调 LLM），`match_score ≥ 75 且 green → 推荐`，`≥60 且非 red → 待定`，其余 → 不推荐

关键文件：
- `backend/agents/graph.py` — 状态图编译（全局单例 `resume_screening_graph`）
- `backend/agents/state.py` — `AgentState` TypedDict，所有节点通过它共享数据
- `backend/agents/nodes/` — 每个节点一个文件
- `backend/services/application_service.py` — `run_screening_pipeline()` 编排触发、异常恢复、结果落库

### 数据流

候选人投递 → `POST /api/candidate/apply`（仅保存，不触发流水线）
→ 手动调用 `POST /api/hr/applications/{id}/rescreen` 触发 Agent 流水线
→ 决策结果写回 `applications` 表，分析详情写入 `agent_results` 表
→ 通过的候选人通过 `feishu_service.py` 推送到飞书群聊

### 数据模型

- **Application**（applications 表）：核心业务表，状态机 `pending → processing → passed/pending_review/rejected`
- **Job**（jobs 表）：岗位含 JD 文本、关键词数组、匹配权重 JSON
- **AgentResult**（agent_results 表）：流水线输出 JSON（打分、亮点、风险、报告）
- **HrUser / Candidate**：用户表，候选人以邮箱去重

### LLM 调用模式

- 通过 OpenAI SDK 以兼容模式调用 DeepSeek API（`backend/utils/deepseek_client.py`）
- 所有 Agent 节点直接调 `client.chat.completions.create`，**不走 function calling / tool_use 流程**
- LLM 返回 JSON 字符串，各节点自行 `json.loads()` 并清理 markdown 代码块包裹
- `backend/agents/tool_executor.py` 和 `backend/agents/tools/` 保留工具定义，但当前未被节点实际调用，是为未来升级预留

### API 路由

| 路由前缀 | 文件 | 端口 |
|---------|------|-----|
| `/api/candidate` | `backend/api/candidate.py` | 候选人投递与状态查询 |
| `/api/hr` | `backend/api/hr.py` | HR 后台管理（认证、岗位、筛选） |
| `/api/jobs` | `backend/api/jobs.py` | 岗位公开浏览 |
| `/api/health` | `backend/main.py` | 健康检查 |

### 配置

`backend/config.py` 从环境变量读取全部配置，阈值和模型名均可通过 `.env` 覆盖。关键变量：`PASS_THRESHOLD=75`、`REVIEW_THRESHOLD=60`、`AGENT_MAX_ITERATIONS=5`。

## 设计决策与约束

1. **approver 必须是规则决策**：不用 LLM，保证结果确定性
2. **reporter 有降级方案**：LLM 异常时 `_fallback_report()` 直接拼装 Markdown，不中断流水线
3. **流水线异常不抛异常**：`run_screening_pipeline` 捕获所有异常，回滚 status 到 pending 并通过返回 dict 的 error 字段传递
4. **投递不自动触发流水线**：需手动调用 rescreen 接口（避免大文件上传阻塞响应）
5. **JWT Secret 临时复用 DEEPSEEK_API_KEY**：`backend/services/auth_service.py:36`，生产环境需独立配置
6. **sync DB 在 async handler 中**：`application_service.py` 的同步 SQLAlchemy 操作在 async 函数里直接调用，生产建议用 `run_in_executor` 或 asyncpg
7. **预留工具调用架构**：`tool_executor.py` + `tools/` 目录是函数调用体系，当前节点未实际使用，未来可迁移到 tool_use 模式
