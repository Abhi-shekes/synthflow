from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "SynthFlow"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./synthflow.db"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    MAX_GENERATE_ROWS: int = 5000
    MAX_LOOKUP_ROWS: int = 5000
    # Jobs stream to disk rather than building a response in memory, so
    # their ceiling is about disk and patience, not RAM — hence far higher
    # than MAX_GENERATE_ROWS, which caps a single interactive response.
    MAX_JOB_ROWS: int = 50_000_000
    # How many rows of an uploaded sample to profile. Distribution fitting
    # converges well before this; reading more mostly costs memory.
    MAX_PROFILE_ROWS: int = 100_000
    JOB_ARTIFACT_DIR: str = "/tmp/synthflow-jobs"
    # How long the in-process worker waits when there was nothing to do.
    WORKER_POLL_SECONDS: float = 2.0
    # The API process also runs the job worker by default. Turned off in
    # the test suite (conftest) so a background loop can't race
    # assertions, and available for anyone wanting API-only replicas.
    RUN_WORKER: bool = True

    # Record every mutating request against the caller who made it. On by
    # default because an audit log nobody switched on is not an audit log,
    # and off is a supported choice for a throwaway instance that would
    # rather not pay a write per mutation.
    AUDIT_LOG: bool = True


settings = Settings()
