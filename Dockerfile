# DisparaAI Production Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies and UV
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# Copy requirements first for better caching
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash disparaai && \
    chown -R disparaai:disparaai /app
USER disparaai

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]