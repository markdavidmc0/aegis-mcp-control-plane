FROM python:3.12-slim

WORKDIR /app

# 1. Install compilation toolchains (LLVM, Clang, Verilog for microkernels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang llvm iverilog build-essential curl git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. Security Hardening & sandbox mount directory
RUN useradd -m -u 1000 appuser && mkdir -p /app/examples/tools/bin

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src:/app" \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# 3. Layer Caching
COPY pyproject.toml uv.lock ./
COPY src/data_plane/pyproject.toml ./src/data_plane/
RUN uv sync --frozen --no-dev --package data-plane --no-install-project

# 4. Copy source & set permissions
COPY src ./src
RUN uv sync --frozen --no-dev --package data-plane && chown -R appuser:appuser /app

USER appuser
EXPOSE 8001

CMD ["uvicorn", "data_plane.mcp_server:app", "--host", "0.0.0.0", "--port", "8001"]
