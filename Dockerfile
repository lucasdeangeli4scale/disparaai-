FROM python:3.11-slim

# Basic python env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system packages required to build some Python packages
# keep the layer small and clean apt lists afterwards
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build helpers
RUN python -m pip install --upgrade pip setuptools wheel

# Copy pyproject first to leverage docker cache for deps
COPY pyproject.toml ./

# Install the package and its dependencies
# This will use the pyproject.toml [build-system] to obtain build backend
RUN python -m pip install --no-cache-dir .

# Copy application source
COPY . .

# Create non-root user and fix permissions
RUN useradd --create-home --shell /bin/bash disparaai \
 && chown -R disparaai:disparaai /app
USER disparaai

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

# Run Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]