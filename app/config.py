from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Samitex Planta"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str

    @property
    def DOCS_URL(self) -> str | None:
        return "/api/docs" if self.APP_ENV != "production" else None

    @property
    def REDOC_URL(self) -> str | None:
        return "/api/redoc" if self.APP_ENV != "production" else None

    # Base de datos — en producción, DATABASE_URL_OVERRIDE reemplaza todo lo de abajo
    DATABASE_URL_OVERRIDE: str = ""      # ej. postgresql://user:pass@host/db (Supabase)
    DB_SERVER: str = ""
    DB_NAME: str = ""
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DB_TRUSTED_CONNECTION: bool = True   # Windows Auth
    DB_USER: str = ""
    DB_PASSWORD: str = ""

    # Supabase Storage
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_BUCKET: str = "uploads"

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # Archivos
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 20

    # WebSocket
    WS_HEARTBEAT_SECONDS: int = 30

    # Bot Telegram + Gemini
    TELEGRAM_TOKEN: str = ""
    GEMINI_API_KEY: str = ""
    NGROK_URL: str = ""
    TELEGRAM_ALLOWED_IDS: str = ""
    BOT_SECRET_KEY: str = ""  # Clave exclusiva para endpoints internos del bot

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        driver = self.DB_DRIVER.replace(" ", "+")
        if self.DB_TRUSTED_CONNECTION:
            return (
                f"mssql+pyodbc://@{self.DB_SERVER}/{self.DB_NAME}"
                f"?driver={driver}&trusted_connection=yes"
            )
        return (
            f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_SERVER}/{self.DB_NAME}"
            f"?driver={driver}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True   # campos y vars en MAYUSCULAS; evita
                                # conflictos entre pydantic-settings 2.7 y 2.14+


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
