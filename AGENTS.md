# Repository Guidelines

## Project Structure & Module Organization
`backend/` 存放 FastAPI 应用、LangGraph 筛选流程、服务层、SQLAlchemy 模型与 API 路由；Agent 节点集中在 `backend/agents/nodes/`，公共工具在 `backend/utils/`，测试位于 `backend/tests/`。`frontend/` 是 Vue 3 前端，候选人与 HR 页面分别放在 `frontend/src/views/candidate/` 和 `frontend/src/views/hr/`。根目录下的 `docker-compose.yml`、`Dockerfile`、`.env.example`、`requirements.txt` 负责本地基础设施与运行依赖。

## Build, Test, and Development Commands
- `pip install -r requirements.txt`：安装后端依赖。
- `uvicorn backend.main:app --reload --port 8000`：在本地启动 FastAPI，端口为 8000。
- `arq backend.services.task_queue.WorkerSettings --watch backend`：启动后台异步任务 Worker。
- `cd frontend && npm run dev`：启动 Vite 开发服务，默认端口 3000。
- `cd frontend && npm run build`：构建前端产物到 `frontend/dist/`。
- `docker-compose up -d`：一键拉起 PostgreSQL、Redis、Chroma、backend 和 worker，便于联调。

## Coding Style & Naming Conventions
Python 使用 4 空格缩进，Vue/JavaScript 使用 2 空格缩进。导入顺序保持“框架/第三方在上，项目内模块在下”。JavaScript 优先使用 `const` 定义函数表达式，避免随意改成声明式 `function`。文件名保持小写；Python 模块用 snake_case，Vue 页面沿用现有命名方式。修改时尽量最小化，只触达当前需求涉及的模块。

## Testing Guidelines
后端测试使用 `pytest`、`pytest-asyncio`、`pytest-cov`。提交前建议运行 `pytest backend/tests -v --cov=backend --cov-report=term-missing`，并执行 `ruff check backend/ --ignore E501`，因为 CI 会校验这些内容。新增测试请放在 `backend/tests/`，命名采用 `test_<feature>.py`。前端改动至少要通过 `cd frontend && npm run build`；如果没有自动化 UI 测试，请在 PR 中补充手工验证说明。

## Commit & Pull Request Guidelines
当前仓库没有可参考的历史提交约定，建议使用简短祈使句，例如 `backend: tighten application status reset` 或 `frontend: fix hr dashboard route`。每次提交只聚焦一个问题。PR 需要写清楚：问题背景、具体改动、验证步骤，以及是否影响配置或 API。涉及可见界面变更时附截图；新增环境变量时请明确列出用途。

## Security & Configuration Tips
本地开发请先复制 `.env.example` 为 `.env`，严禁提交真实密钥。`uploads/` 中的简历文件和根目录下的 `tmp*` 临时产物都应视为本地调试数据，不要纳入版本控制。
