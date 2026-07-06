FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema (compilação de wheels de ML: sentence-transformers etc.)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Cache do HuggingFace dentro da imagem: o modelo de embeddings é baixado no
# build e reutilizado em runtime (sem download no cold start do Cloud Run).
ENV HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1

# Dependências Python primeiro (camada cacheável)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação + snapshot oficial da BNCC (data/bncc_v1.json)
COPY . .

# Embeddings "assados" na imagem: derivados não-oficiais (Princípio IV/VII) do
# snapshot versionado, gerados de forma determinística no build. O filesystem do
# Cloud Run é efêmero/read-only, então o índice ChromaDB precisa vir pronto.
RUN mkdir -p /app/data \
    && python scripts/generate_embeddings.py --reset

# O Cloud Run injeta a porta em $PORT (default 8080); localmente cai para 8000.
# --proxy-headers/--forwarded-allow-ips: atrás do proxy TLS do Cloud Run, honra
# X-Forwarded-Proto para request.base_url gerar URLs https (canonical/og:url).
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
