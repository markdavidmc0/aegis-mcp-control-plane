FROM python:3.12-slim

WORKDIR /app

# 1. Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. Add virtual environment and src to PATH / PYTHONPATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src:/app" \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# 3. Copy workspace metadata and lockfiles for Docker layer caching
COPY pyproject.toml uv.loc[k] ./
COPY src/control_plane/pyproject.toml ./src/control_plane/

# 4. CACHE LAYER: Sync dependencies without installing project source code
RUN uv sync --frozen --no-dev --package control-plane --no-install-project

# 5. Copy full source code and execute final workspace sync
COPY src ./src
RUN uv sync --frozen --no-dev --package control-plane

EXPOSE 8000

CMD ["uvicorn", "control_plane.main:app", "--host", "0.0.0.0", "--port", "8000"]
