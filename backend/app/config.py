from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="")

    app_env: str = "dev"
    jwt_secret: str
    jwt_exp_days: int = 30

    matching_max_wait_seconds: int = 30
    pending_accept_timeout_seconds: int = 20
    session_duration_seconds: int = 300
    session_grace_period_seconds: int = 5

    max_ws_per_token: int = 2
    max_ws_per_ip: int = 10
    idle_timeout_seconds: int = 60

    max_message_bytes: int = 2000
    max_messages_per_min: int = 60

    seeker_session_rate_per_hour: int = 5
    volunteer_accept_rate_per_hour: int = 60

    ip_block_threshold_score: int = 10
    ip_block_duration_minutes: int = 60

    log_retention_days: int = 30
    metrics_retention_days: int = 365

    fcm_server_key: str | None = None
    redis_url: str | None = "redis://localhost:6379/0"
    db_url: str | None = None

    abuse_end_session_threshold: int = 2
    abuse_ban_threshold: int = 3
    self_harm_crisis_threshold: int = 2
    incident_retention_days: int = 90
    ban_retention_days: int = 365
    admin_jwt_secret: str | None = None
    crisis_resource_message: str = (
        "If you are in immediate danger or thinking about self-harm, please contact local emergency services "
        "or a crisis hotline in your area."
    )
    crisis_resource_messages: dict[str, str] = {}

    def crisis_message(self, locale: str | None) -> str:
        if locale:
            normalized = locale.lower().split("-")[0]
            if normalized in self.crisis_resource_messages:
                return self.crisis_resource_messages[normalized]
        return self.crisis_resource_message

    def public_config(self) -> dict[str, int]:
        """Values safe to expose to clients."""
        return {
            "session_duration_seconds": self.session_duration_seconds,
            "matching_max_wait_seconds": self.matching_max_wait_seconds,
            "timer_sync_interval_seconds": 5,
            "max_message_length": self.max_message_bytes,
        }


settings = Settings()  # Loaded at import for simplicity; FastAPI will use dependency injection.
