# ============================================================
# ResumeVane 后端 Docker 镜像
# ============================================================
# 基于 Python 3.12 slim 镜像（体积小，适合生产部署）
# 构建: docker build -t resumevane:latest .
# 注意: 构建前确保 .env 文件已配置（被 COPY 进镜像）
# ============================================================

FROM python:3.12-slim

# 设置工作目录——所有后续命令在此目录执行
WORKDIR /app

# ── 安装依赖 ────────────────────────────────────────
# 先单独 COPY requirements.txt 以利用 Docker 层缓存
# 如果依赖不变，pip install 层会被缓存，加速后续构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 复制应用代码 ─────────────────────────────────────
COPY backend/ ./backend/
# Do not bake local secrets into the image; provide runtime environment variables instead.

# ── 启动配置 ─────────────────────────────────────────
EXPOSE 8000

# uvicorn 启动 FastAPI
# --host 0.0.0.0: 监听所有网络接口（容器内必须）
# --port 8000:   对应 EXPOSE 和 docker-compose 映射的端口
# 生产环境建议加 --workers 4 以利用多核（配合 guvicorn 需改为 gunicorn + uvicorn worker）
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
