# DisparaAI - Production Dockerfile
FROM python:3.11-slim

# Configs básicas do Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências de sistema + curl (healthcheck) + UV
RUN apt-get update && apt-get install -y --no-install-recommends \
  gcc g++ libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# 'uv' is not a real dependency; install only system packages and curl

# Instala deps do projeto a partir do pyproject (melhor cache)
COPY pyproject.toml ./
# Install project dependencies from pyproject using pip
# use python -m pip to ensure correct interpreter and avoid stray 'uv' prefix
RUN python -m pip install --no-cache-dir .

# Copia o código
COPY . .

# Usuário não-root
RUN useradd --create-home --shell /bin/bash disparaai \
 && chown -R disparaai:disparaai /app
USER disparaai

EXPOSE 8000

# Healthcheck da API
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

# Sobe o servidor FastAPI (main:app está na raiz do repo)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
