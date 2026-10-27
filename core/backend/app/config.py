from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    env: str = "production"
    secret_key: str = "change-me"

    database_url: str = "postgresql+asyncpg://vaksina:vaksina@db:5432/vaksina"
    redis_url: str = "redis://redis:6379/0"

    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30
    # 'auto': HTTPS bo'lsa Secure cookie (proxy X-Forwarded-Proto orqali)
    cookie_secure: str = "auto"

    # Fayl saqlash (MinIO, S3-mos). Kalitlar .env dagi MINIO_ROOT_USER/PASSWORD
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = ""
    minio_root_password: str = ""
    minio_bucket: str = "vaksina"
    minio_secure: bool = False

    # Telegram: bo'sh token = Telegram o'chirilgan (bot va yuborish ishlamaydi)
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""  # ixtiyoriy; bo'sh bo'lsa bot getMe orqali aniqlaydi
    # Bildirishnomalardagi havolalar uchun, masalan https://client1.vaksinahr.uz
    public_url: str = ""

    # Qo'ng'iroq (LiveKit). Kalit bo'sh bo'lsa qo'ng'iroqlar o'chirilgan
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_internal_url: str = "http://livekit:7880"
    livekit_public_url: str = ""  # bo'sh: brauzer o'z domenidagi /livekit ga ulanadi

    # AI (Claude API). Kalit bo'sh bo'lsa AI o'chirilgan, tizim qoidalar asosida ishlayveradi
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    ai_default_model: str = "claude-haiku-5-5"

    # Xavfsizlik: IP bo'yicha so'rov chastotasi (hardening.RULES), koeffitsiyent bilan o'zgartiriladi
    rate_limit_enabled: bool = True
    rate_limit_multiplier: float = 1.0
    # /api/metrics (Prometheus): token berilsa Bearer shart, berilmasa faqat ichki tarmoqdan (gateway orqali emas)
    metrics_token: str = ""
    # OpenAPI hujjati (/api/docs) productionda o'chiq; yoqish: API_DOCS=true
    api_docs: bool = False

    # Ish vaqti hisobi (smena, davomat, hisobotlar) shu mintaqa bo'yicha
    timezone: str = "Asia/Tashkent"

    # PDF hisobotlar shrifti (Docker imidjida /opt/models/fonts)
    font_dir: str = "/opt/models/fonts"

    # Javob olish: koordinator shuncha soat ichida javob bermasa, so'rov HR ga o'tadi
    answers_escalation_hours: int = 8

    # Face ID
    face_model_dir: str = "/opt/models"
    # Shifrlash kaliti (shablonlar). Bo'sh bo'lsa SECRET_KEY dan olinadi; prod da alohida qo'yish tavsiya etiladi
    face_encryption_key: str = ""
    face_match_threshold: float = 0.40  # kosinus o'xshashlik; /face/evaluation da FAR/FRR bo'yicha tanlanadi
    face_duplicate_threshold: float = 0.50  # boshqa xodim bilan shundan yuqori bo'lsa ro'yxatga olinmaydi
    face_retention_days: int = 365  # oxirgi yangilash/tekshiruvdan keyin shablon o'chiriladi
    face_dismissed_retention_days: int = 30  # xodim bo'shatilgach shablon saqlanadi
    face_consent_version: str = "2026-10-v1"

    # Mijoz (client) extension joylashgan papka: <clients>/<name>
    client_name: str = "example"
    client_dir: str = "/clients/example"

    @property
    def is_dev(self) -> bool:
        return self.env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
