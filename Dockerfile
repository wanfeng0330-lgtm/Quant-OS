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

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install dependencies (no dev deps)
RUN uv sync --frozen --no-dev

# Set working directory to API
WORKDIR /app/apps/api

# Expose port
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
