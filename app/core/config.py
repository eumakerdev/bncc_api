"""
Application configuration settings.

Princípio V (Segurança por padrão) / FR-023: nenhum default inseguro pode subir
em produção. Em ENVIRONMENT=production a aplicação FALHA RÁPIDO na inicialização
se SECRET_KEY for placeholder/ausente ou se ALLOWED_HOSTS contiver "*".
"""

from urllib.parse import quote, urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de placeholder que NUNCA podem subir em produção.
INSECURE_SECRET_PLACEHOLDERS = {
    "",
    "change-me-dev-only-not-for-production",
    "your-secret-key-change-in-production",
    "your-very-secret-key-change-in-production-please",
}


class Settings(BaseSettings):
    """Application settings carregadas de ambiente / arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # --- Ambiente ---
    ENVIRONMENT: str = Field(default="development", description="development | production")
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    LOG_LEVEL: str = Field(default="INFO")

    # --- Segurança ---
    SECRET_KEY: str = Field(default="change-me-dev-only-not-for-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    # Sessão do portal (login persistente): duração do JWT de sessão E do cookie
    # `__session`. Longa por padrão (30 dias) para que o login sobreviva a fechar/
    # reabrir janelas e abas — sem exigir novo login a cada hora.
    SESSION_EXPIRE_MINUTES: int = Field(default=60 * 24 * 30)
    ALLOWED_HOSTS: list[str] = Field(default=["*"])

    # --- Superfície pública / SEO ---
    # URL canônica do site. Vazio em dev = deriva de `request.base_url`. Em produção
    # deve apontar para o domínio primário (ex.: https://bncc.api.br) para que
    # canonical/OG/sitemap/robots NÃO vazem a URL interna do Cloud Run: atrás do
    # Firebase Hosting o container recebe o `Host` do `.run.app`, não o domínio público.
    SITE_URL: str = Field(default="")

    # --- Banco da plataforma ---
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data/platform.db")
    # Senha do banco injetada via secret (Cloud SQL / produção). Quando definida,
    # substitui o placeholder literal `__DB_PASSWORD__` em DATABASE_URL. Assim a
    # senha nunca trafega em texto plano na variável de ambiente (Princípio V).
    DB_PASSWORD: str = Field(default="")

    # --- Dados oficiais da BNCC (snapshot versionado, read-only) ---
    BNCC_DATA_PATH: str = Field(default="./data/bncc_v1.json")
    CHROMADB_PATH: str = Field(default="./data/chromadb")

    # --- E-mail ---
    EMAIL_BACKEND: str = Field(default="console", description="console | smtp")
    EMAIL_FROM: str = Field(default="no-reply@bncc.example.com")
    EMAIL_VERIFICATION_BASE_URL: str = Field(default="http://localhost:8000/portal/verify-email")
    EMAIL_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)
    # Redefinição de senha ("esqueci a senha"): página do portal que consome o token.
    PASSWORD_RESET_BASE_URL: str = Field(default="http://localhost:8000/portal/reset-password")
    # Token de reset é sensível (troca de credencial) → janela curta.
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    SMTP_HOST: str = Field(default="")
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_USE_TLS: bool = Field(default=True)

    # --- Cotas / Rate limiting (FR-010/FR-010a) ---
    RATE_LIMIT_DETERMINISTIC_PER_MIN: int = Field(default=60)
    RATE_LIMIT_DETERMINISTIC_BURST: int = Field(default=10)
    RATE_LIMIT_AI_PER_MIN: int = Field(default=20)
    RATE_LIMIT_AI_PER_DAY: int = Field(default=500)

    # --- Rate limiting por IP dos endpoints de sessão (sem API key) ---
    # Protege login/signup/verify-email contra força bruta e spam de contas,
    # já que estes endpoints não passam pela cota por API key (deps.py).
    RATE_LIMIT_LOGIN_PER_MIN: int = Field(default=10)
    RATE_LIMIT_SIGNUP_PER_MIN: int = Field(default=5)
    RATE_LIMIT_VERIFY_PER_MIN: int = Field(default=30)
    RATE_LIMIT_OAUTH_PER_MIN: int = Field(default=10)
    # "Esqueci a senha": dispara e-mail com token → coíbe spam/enumeração por IP.
    RATE_LIMIT_FORGOT_PER_MIN: int = Field(default=5)

    # --- Login social (OAuth 2.0) — opcional; desabilita se não configurado ---
    # Secrets carregados do ambiente (Princípio V). Ambos os campos de um provedor
    # devem ser definidos juntos; em produção, id-sem-secret (ou vice-versa) é
    # bloqueado por _enforce_production_security.
    GOOGLE_OAUTH_CLIENT_ID: str = Field(default="")
    GOOGLE_OAUTH_CLIENT_SECRET: str = Field(default="")
    GITHUB_OAUTH_CLIENT_ID: str = Field(default="")
    GITHUB_OAUTH_CLIENT_SECRET: str = Field(default="")
    # Base pública usada para montar o redirect_uri do callback OAuth.
    OAUTH_REDIRECT_BASE_URL: str = Field(default="http://localhost:8000")

    # --- Painel de administração (local only, Princípio V) ---
    # Vazio = painel de admin desabilitado (default seguro). Defina com uma senha
    # forte para habilitar o painel em `/admin` — nunca use em produção sem HTTPS
    # e restrição de rede. O painel não é publicado nem registrado no OpenAPI.
    ADMIN_PASSWORD: str = Field(default="")

    @property
    def admin_enabled(self) -> bool:
        return bool(self.ADMIN_PASSWORD)

    # --- Transparência de custos (BigQuery billing export; opcional) ---
    # Vazio = ingestão de custos desligada. São apenas leitura de números públicos
    # (custo de infraestrutura), então NÃO entram no fail-fast de produção. Usados só
    # pelo job agendado `scripts/ingest_costs.py`; o app web nunca toca o BigQuery.
    GCP_PROJECT: str = Field(default="")
    GCP_BILLING_DATASET: str = Field(default="")
    GCP_BILLING_TABLE: str = Field(default="")
    # Fallback de conversão caso o export venha em outra moeda que não BRL (conta
    # de billing brasileira fatura em BRL → normalmente não é necessário). 0 = sem
    # conversão (assume BRL).
    USD_BRL_RATE: float = Field(default=0.0)

    # --- IA / Busca semântica (opcional; degrada graciosamente) ---
    OPENAI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")
    # Modelo multilíngue: a BNCC é em português; modelos só-inglês (all-MiniLM)
    # casam componentes curriculares errados. Este modelo retorna os corretos.
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    LLM_MODEL: str = Field(default="gpt-3.5-turbo")
    # Calibrado para o modelo multilíngue: acertos relevantes pontuam ~0,50–0,72.
    SIMILARITY_THRESHOLD: float = Field(default=0.45)
    MAX_SEARCH_RESULTS: int = Field(default=10)
    AI_REQUEST_TIMEOUT_SECONDS: int = Field(default=15)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=800)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_OAUTH_CLIENT_ID and self.GOOGLE_OAUTH_CLIENT_SECRET)

    @property
    def github_oauth_enabled(self) -> bool:
        return bool(self.GITHUB_OAUTH_CLIENT_ID and self.GITHUB_OAUTH_CLIENT_SECRET)

    @property
    def TRUSTED_HOSTS(self) -> list[str]:
        """Hostnames puros para o `TrustedHostMiddleware`, derivados de
        `ALLOWED_HOSTS`. Este último guarda *origins* com scheme (`https://host`),
        o formato exigido pelo CORS; já o TrustedHost compara com o header `Host`,
        que chega sem scheme e sem porta. Extraímos o hostname de cada entrada para
        que uma única env var sirva aos dois middlewares."""
        hosts: list[str] = []
        for entry in self.ALLOWED_HOSTS:
            if entry == "*":
                hosts.append("*")
                continue
            # urlsplit só popula netloc quando há "//"; caso contrário é host puro.
            host = urlsplit(entry).hostname if "://" in entry else entry.split(":")[0].strip()
            if host:
                hosts.append(host)
        return hosts

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def _split_allowed_hosts(cls, v: object) -> object:
        # Aceita "a,b" além de lista/JSON, para ergonomia de env.
        if isinstance(v, str) and not v.strip().startswith("["):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _inject_db_password(self) -> "Settings":
        """Injeta a senha do banco (secret) no placeholder de DATABASE_URL."""
        if self.DB_PASSWORD and "__DB_PASSWORD__" in self.DATABASE_URL:
            self.DATABASE_URL = self.DATABASE_URL.replace(
                "__DB_PASSWORD__", quote(self.DB_PASSWORD, safe="")
            )
        return self

    @model_validator(mode="after")
    def _enforce_production_security(self) -> "Settings":
        """Fail-fast em produção com configuração insegura (FR-023 / SC-010)."""
        if not self.is_production:
            return self

        errors: list[str] = []
        if self.SECRET_KEY in INSECURE_SECRET_PLACEHOLDERS or len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY ausente, placeholder ou fraca (mínimo 32 chars) em produção")
        if "*" in self.ALLOWED_HOSTS:
            errors.append('ALLOWED_HOSTS não pode conter "*" em produção')
        for name, cid, secret in (
            ("Google", self.GOOGLE_OAUTH_CLIENT_ID, self.GOOGLE_OAUTH_CLIENT_SECRET),
            ("GitHub", self.GITHUB_OAUTH_CLIENT_ID, self.GITHUB_OAUTH_CLIENT_SECRET),
        ):
            if bool(cid) != bool(secret):
                errors.append(
                    f"OAuth {name}: client_id e client_secret devem ser ambos "
                    "definidos ou ambos vazios"
                )

        if errors:
            raise ValueError(
                "Configuração insegura bloqueada (Princípio V / FR-023): " + "; ".join(errors)
            )
        return self


# Global settings instance (validado na importação — fail-fast)
settings = Settings()
