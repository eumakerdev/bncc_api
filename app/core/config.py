"""
Application configuration settings.

Princípio V (Segurança por padrão) / FR-023: nenhum default inseguro pode subir
em produção. Em ENVIRONMENT=production a aplicação FALHA RÁPIDO na inicialização
se SECRET_KEY for placeholder/ausente ou se ALLOWED_HOSTS contiver "*".
"""


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
    ALLOWED_HOSTS: list[str] = Field(default=["*"])

    # --- Banco da plataforma ---
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data/platform.db")

    # --- Dados oficiais da BNCC (snapshot versionado, read-only) ---
    BNCC_DATA_PATH: str = Field(default="./data/bncc_v1.json")
    CHROMADB_PATH: str = Field(default="./data/chromadb")

    # --- E-mail ---
    EMAIL_BACKEND: str = Field(default="console", description="console | smtp")
    EMAIL_FROM: str = Field(default="no-reply@bncc.example.com")
    EMAIL_VERIFICATION_BASE_URL: str = Field(default="http://localhost:8000/portal/verify-email")
    EMAIL_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)
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

    # --- IA / Busca semântica (opcional; degrada graciosamente) ---
    OPENAI_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")
    EMBEDDING_MODEL: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    LLM_MODEL: str = Field(default="gpt-3.5-turbo")
    SIMILARITY_THRESHOLD: float = Field(default=0.70)
    MAX_SEARCH_RESULTS: int = Field(default=10)
    AI_REQUEST_TIMEOUT_SECONDS: int = Field(default=15)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=800)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def _split_allowed_hosts(cls, v: object) -> object:
        # Aceita "a,b" além de lista/JSON, para ergonomia de env.
        if isinstance(v, str) and not v.strip().startswith("["):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

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

        if errors:
            raise ValueError(
                "Configuração insegura bloqueada (Princípio V / FR-023): " + "; ".join(errors)
            )
        return self


# Global settings instance (validado na importação — fail-fast)
settings = Settings()
