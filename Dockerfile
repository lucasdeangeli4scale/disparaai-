#----------------------------------------------------------------#
# Estágio 1: "Builder" - Onde usamos 'uv' para instalar tudo
#----------------------------------------------------------------#
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instala dependências de sistema para construir pacotes Python (como psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cria um ambiente virtual que será copiado para a imagem final
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instala o 'uv' usando pip
RUN pip install uv

# Copia o arquivo de dependências
COPY pyproject.toml ./

# Usa 'uv' para instalar todas as dependências do projeto. É MUITO mais rápido!
RUN uv pip install --system .


#----------------------------------------------------------------#
# Estágio 2: "Final" - A imagem limpa que irá para produção
#----------------------------------------------------------------#
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala apenas as dependências de sistema para RODAR a aplicação
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Copia o ambiente virtual com as dependências já instaladas pelo 'uv'
COPY --from=builder /opt/venv /opt/venv

# Copia o código da aplicação
COPY . .

# Cria e usa o usuário não-root
RUN useradd --create-home --shell /bin/bash disparaai \
 && chown -R disparaai:disparaai /app /opt/venv
USER disparaai

# Ativa o ambiente virtual para os comandos seguintes
ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]