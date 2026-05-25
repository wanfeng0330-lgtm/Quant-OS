FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy workspace config first for layer caching
COPY pyproject.toml uv.lock ./

# Copy all workspace packages
COPY packages/ packages/

# Copy API app
COPY apps/api/ apps/api/

# Install dependencies (no dev deps)
RUN uv sync --frozen --no-dev

# Set working directory to API
WORKDIR /app/apps/api

# Start server on port 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
