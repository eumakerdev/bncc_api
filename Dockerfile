FROM python:3.11-slim

WORKDIR /app

# Cache do HuggingFace dentro da imagem: o modelo de embeddings é baixado no
# build e reutilizado em runtime (sem download no cold start do Cloud Run).
ENV HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1

# Dependências de sistema apenas para COMPILAR as wheels de ML (sentence-transformers
# etc.) e removidas em seguida: gcc/g++ não são necessários em runtime, então sair
# com eles só aumentaria a superfície de ataque da imagem (Princípio V). O gate de
# build do CI (`docker build`) executa `generate_embeddings.py` abaixo — que importa
# toda a stack de IA — DEPOIS da remoção, provando que nada em runtime depende deles.
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Código da aplicação + snapshot oficial da BNCC (data/bncc_v1.json)
COPY . .

# Embeddings "assados" na imagem: derivados não-oficiais (Princípio IV/VII) do
# snapshot versionado, gerados de forma determinística no build. O filesystem do
# Cloud Run é efêmero/read-only, então o índice ChromaDB precisa vir pronto.
RUN mkdir -p /app/data \
    && python scripts/generate_embeddings.py --reset

# Runtime sem privilégios (Princípio V — menor privilégio): o processo NUNCA roda
# como root. `appuser` passa a dono de /app (código, snapshot, cache HF, índice
# ChromaDB já assados acima) para conseguir lê-los; o filesystem do Cloud Run é
# read-only fora de /tmp, então não há escrita a proteger além disso.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# O Cloud Run injeta a porta em $PORT (default 8080); localmente cai para 8000.
# --proxy-headers/--forwarded-allow-ips: atrás do proxy TLS do Cloud Run, honra
# X-Forwarded-Proto para request.base_url gerar URLs https (canonical/og:url).
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
