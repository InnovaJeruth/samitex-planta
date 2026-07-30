from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Samitex Planta"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str

    # Hosts permitidos (cabecera Host). CSV; "*" = todos (default, no bloquea).
    # En producción, poner los hosts reales, p.ej: "erp.samitex.local,10.0.0.5"
    ALLOWED_HOSTS: str = "*"

    @property
    def ALLOWED_HOSTS_LIST(self) -> list[str]:
        v = (self.ALLOWED_HOSTS or "*").strip()
        if v == "*":
            return ["*"]
        return [h.strip() for h in v.split(",") if h.strip()]

    @property
    def DOCS_URL(self) -> str | None:
        return "/api/docs" if self.APP_ENV != "production" else None

    @property
    def REDOC_URL(self) -> str | None:
        return "/api/redoc" if self.APP_ENV != "production" else None

    @property
    def OPENAPI_URL(self) -> str | None:
        return "/api/openapi.json" if self.APP_ENV != "production" else None

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
    JWT_EXPIRE_MINUTES: int = 240        # 4 horas

    # Seguridad de red: confiar en X-Forwarded-For SOLO si hay un proxy confiable delante
    TRUST_PROXY: bool = False

    # Archivos
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 20

    # Máx. de tareas CPU-bound en paralelo (PDF, import Excel, process mining).
    # Evita que varias a la vez saturen el proceso por el GIL de Python.
    HEAVY_MAX_CONCURRENCIA: int = 2

    # Bot Telegram + Gemini
    TELEGRAM_TOKEN: str = ""
    GEMINI_API_KEY: str = ""
    NGROK_URL: str = ""
    TELEGRAM_ALLOWED_IDS: str = ""
    BOT_SECRET_KEY: str = ""  # Clave exclusiva para endpoints internos del bot

    # RAG / Chat analítico (Text-to-SQL, solo lectura)
    RAG_ENABLED: bool = False
    # Cadena de conexión de SOLO LECTURA (login db_datareader dedicado).
    # Si queda vacía, se usa DATABASE_URL (barreras solo a nivel app).
    RAG_DB_URL: str = ""
    RAG_LLM_PROVIDER: str = "gemini"      # gemini (nube) | ollama (local, gratis)
    RAG_MODEL: str = "gemini-2.0-flash"   # modelo Gemini para generar SQL / resumen
    RAG_OLLAMA_URL: str = "http://localhost:11434"     # endpoint de Ollama
    RAG_OLLAMA_MODEL: str = "qwen2.5-coder:7b"          # modelo local para SQL
    RAG_MAX_ROWS: int = 200               # tope de filas por consulta (SELECT TOP N)
    RAG_QUERY_TIMEOUT: int = 20           # segundos máx. por consulta SQL
    RAG_LLM_TIMEOUT: int = 30             # segundos máx. por llamada al LLM
    RAG_INCLUIR_RESUMEN: bool = True      # 2ª llamada al LLM para redactar la respuesta
    # Máx. de consultas RAG al LLM en vuelo a la vez. Evita que el chat agote el
    # threadpool de FastAPI (compartido con el resto de endpoints) bajo carga.
    RAG_MAX_CONCURRENCIA: int = 3

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            # psycopg2 no entiende el param ?pgbouncer=true de Supabase
            url = self.DATABASE_URL_OVERRIDE
            url = url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
            return url
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

    @property
    def RAG_DATABASE_URL(self) -> str:
        """Conexión de solo lectura para el chat analítico. Usa el login
        dedicado (db_datareader) si está configurado; si no, cae a DATABASE_URL."""
        return self.RAG_DB_URL.strip() or self.DATABASE_URL

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True   # campos y vars en MAYUSCULAS; evita
                                # conflictos entre pydantic-settings 2.7 y 2.14+


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
