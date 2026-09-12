from functools import lru_cache
import os


class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./securevoice.db")
    redis_url = os.getenv("REDIS_URL", "")
    secret_key = os.getenv("SECRET_KEY", "development-only-secret")
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "change-me-now")
    max_audio_bytes = 2 * 1024 * 1024
    min_audio_seconds = 2.0
    max_audio_seconds = 5.5
    speaker_threshold = 0.82
    spoof_threshold = 0.55
    max_attempts = 5
    lock_seconds = 15 * 60


@lru_cache
def settings() -> Settings:
    return Settings()
