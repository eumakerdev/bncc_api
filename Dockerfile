FROM python:3.11-slim

WORKDIR /app

# Cache do HuggingFace dentro da imagem: o modelo de embeddings é baixado no
# build e reutilizado em runtime (sem download no cold start do Cloud Run).
ENV HF_HOME=/app/.cache/huggingface \
    PYTHONUNBUFFERED=1

# Usuário sem privilégios criado ANTES de copiar qualquer coisa (Princípio V).
# A ordem importa para o tamanho da imagem: um `chown -R /app` depois dos
# artefatos pesados reescreveria a árvore inteira numa camada nova, duplicando o
# cache do HuggingFace e o índice ChromaDB. Com o usuário existindo antes, cada
# COPY/RUN já grava com o dono certo e nenhuma camada é duplicada.
RUN useradd --create-home --uid 10001 appuser

# torch CPU-only, ANTES do requirements.txt. Instalado do índice `+cpu` do
# PyTorch de propósito: a wheel padrão do PyPI para Linux x86_64 embute o runtime
# CUDA da NVIDIA (~2,5 GB de nvidia-cublas/cudnn/etc.) que é inútil no Cloud Run,
# onde não há GPU. Como o torch já sai satisfeito desta camada, o
# `sentence-transformers` do passo seguinte não puxa a variante CUDA.
# A versão acompanha a do ambiente de dev; subir uma exige subir a outra.
RUN pip install --no-cache-dir torch==2.12.1 \
        --index-url https://download.pytorch.org/whl/cpu

# Dependências de sistema apenas para COMPILAR as wheels de ML (sentence-transformers
# etc.) e removidas em seguida: gcc/g++ não são necessários em runtime, então sair
# com eles só aumentaria a superfície de ataque da imagem (Princípio V). O gate de
# build do CI (`docker build`) executa `generate_embeddings.py` abaixo — que importa
# toda a stack de IA — DEPOIS da remoção, provando que nada em runtime depende deles.
#
# Só `requirements.txt`: teste/lint/docs e a stack de extração de PDF vivem em
# `requirements-dev.txt` e não entram na imagem (nada em `app/` as importa).
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Código da aplicação + snapshot oficial da BNCC (data/bncc_v1.json)
COPY --chown=appuser:appuser . .

# `COPY --chown` marca os arquivos COPIADOS, mas não o diretório /app em si, que o
# WORKDIR criou como root. Sem isto o passo seguinte falha com "permission denied"
# ao criar /app/.cache (download do modelo) — appuser não pode escrever em /app.
# É um chown de 3 diretórios, não recursivo: não duplica camada.
RUN mkdir -p /app/data /app/.cache \
    && chown appuser:appuser /app /app/data /app/.cache

# Embeddings "assados" na imagem: derivados não-oficiais (Princípio IV/VII) do
# snapshot versionado, gerados de forma determinística no build. O filesystem do
# Cloud Run é efêmero/read-only, então o índice ChromaDB precisa vir pronto.
# Gerado já como `appuser` para que o índice e o cache HF nasçam com o dono final.
USER appuser
RUN python scripts/generate_embeddings.py --reset

# O Cloud Run injeta a porta em $PORT (default 8080); localmente cai para 8000.
# --proxy-headers/--forwarded-allow-ips: atrás do proxy TLS do Cloud Run, honra
# X-Forwarded-Proto para request.base_url gerar URLs https (canonical/og:url).
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
