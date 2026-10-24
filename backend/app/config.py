from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"  # "production" turns on strict checks
    database_url: str = "sqlite:///./eduvoice.db"
    # Auto-detected from Vercel Supabase integration
    postgres_url: str = ""
    postgres_prisma_url: str = ""
    jwt_secret: str = _DEFAULT_SECRET
    jwt_expire_minutes: int = 60
    cookie_secure: bool = False
    frontend_origin: str = "http://localhost:3000"
    # Signing key: base64 of the PEM (for hosts with no persistent disk). Dev falls back to a key file.
    signing_key_pem_b64: str = ""
    signing_key_path: str = "./signing_key.pem"
    # Privacy thresholds
    min_responses: int = 5          # hide all stats below this many responses
    min_comments_visible: int = 10  # hide free-text comments below this many
    use_hf_models: bool = False

    # Mail (self-signup verification, admin-invite emails). If smtp_host is empty,
    # emails are logged instead of sent — fine for local dev, not for production.
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "EduVoice <no-reply@eduvoice.local>"
    admin_notify_email: str = ""        # optional: pinged when a signup needs approval
    allowed_email_domains: str = ""     # comma-separated; empty = any domain allowed

    # Google sign-in (optional — buttons hide themselves when these are empty)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""  # must exactly match the URI registered in Google Cloud Console

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_redirect_uri)

    @property
    def allowed_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.allowed_email_domains.split(",") if d.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def sqlalchemy_url(self) -> str:
        """Accepts database_url, postgres_url, or postgres_prisma_url from Neon/Supabase Vercel Integration."""
        url = self.database_url
        if not url or url == "sqlite:///./eduvoice.db":
            url = self.postgres_url or self.postgres_prisma_url or "sqlite:///./eduvoice.db"
        url = url.strip()
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    def check_production(self) -> None:
        problems = []
        if self.jwt_secret == _DEFAULT_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be set to a random string of at least 32 characters")
        if not self.signing_key_pem_b64:
            problems.append("SIGNING_KEY_PEM_B64 must be set (run: python -m app.bootstrap genkey)")
        if self.sqlalchemy_url.startswith("sqlite"):
            problems.append("DATABASE_URL or POSTGRES_URL must point to PostgreSQL (SQLite is not persistent on serverless hosts)")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true")
        if problems:
            raise RuntimeError("Unsafe production configuration:\n - " + "\n - ".join(problems))


settings = Settings()
