import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEFAULT_SECRET_KEY = "change-me-in-production"
_MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "SynthFlow"
    API_V1_PREFIX: str = "/api/v1"

    # "production" is the only value that turns the SECRET_KEY check below
    # into a hard failure. Everything else (the default) stays a warning,
    # since a from-scratch local install should still boot without ceremony.
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "sqlite:///./synthflow.db"

    SECRET_KEY: str = _DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    # The refresh token lives in an httpOnly cookie, never in JS-readable
    # storage — see app.api.routes.auth. `None` (the default) means "follow
    # ENVIRONMENT": secure in production, not in development — because
    # `Secure` cookies are simply not sent over a plain-http connection by
    # anything except a browser's own carve-out for http://localhost, and
    # that carve-out doesn't extend to the test client, curl, or the CLI.
    # A real deployment (anything but a laptop) is expected to terminate
    # TLS somewhere, so ENVIRONMENT=production forces this on regardless of
    # what's set here explicitly.
    SESSION_COOKIE_SECURE: bool | None = None

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Every route that accepts a file upload reads it through
    # app.core.uploads.read_capped, which enforces this — see that
    # module's docstring for why the endpoint has to enforce it itself
    # rather than trusting Content-Length.
    MAX_UPLOAD_BYTES: int = 64 * 1024 * 1024

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

    # Single sign-on over OpenID Connect. All three are required together;
    # with any of them empty, SSO is simply off and the password login is
    # the only way in — which is the right default for a local install.
    OIDC_ISSUER: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    # `openid` alone would authenticate someone SynthFlow then has no way to
    # identify: accounts are keyed by email address.
    OIDC_SCOPES: str = "openid email profile"
    OIDC_TIMEOUT_SECONDS: float = 10.0
    # Where the browser lands after a successful sign-in, with tokens in the
    # fragment. Points at the frontend, which is a separate origin.
    OIDC_POST_LOGIN_URL: str = "http://localhost:3000/login"

    @property
    def session_cookie_secure(self) -> bool:
        if self.SESSION_COOKIE_SECURE is not None:
            return self.SESSION_COOKIE_SECURE
        return self.ENVIRONMENT == "production"

    @model_validator(mode="after")
    def _check_secret_key(self) -> "Settings":
        """SECRET_KEY signs every auth token *and* derives the encryption
        key for every stored credential (see app.core.secrets). A default
        or short key means both are trivially forgeable/decryptable by
        anyone who has read the source — which is public. Refuse to boot
        with one in production; warn everywhere else, since local dev
        should still work with zero setup."""
        too_short = len(self.SECRET_KEY) < _MIN_SECRET_KEY_LENGTH
        weak = self.SECRET_KEY == _DEFAULT_SECRET_KEY or too_short
        if not weak:
            return self

        message = (
            "SECRET_KEY is missing, the well-known default, or shorter than "
            f"{_MIN_SECRET_KEY_LENGTH} characters. It signs every access/refresh "
            "token and encrypts every stored database/storage/webhook credential — "
            'generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"` '
            "and set it before deploying. `synthflow init` does this for you."
        )
        if self.ENVIRONMENT == "production":
            raise ValueError(message)
        logger.warning("%s Set ENVIRONMENT=production to make this a hard failure.", message)
        return self

    @model_validator(mode="after")
    def _check_cors_origins(self) -> "Settings":
        """CORSMiddleware is configured with allow_credentials=True (see
        app.main) — combined with a wildcard origin that would let *any*
        site read authenticated responses from a signed-in visitor's
        browser. Browsers already refuse "*" plus credentials, but nothing
        stopped an operator from setting a list of origins broad enough to
        be equivalent (or from setting "*" and getting a browser-side
        failure that looks like a mysterious CORS bug instead of the
        config error it is)."""
        if "*" in self.CORS_ORIGINS:
            raise ValueError(
                'CORS_ORIGINS may not include "*" while allow_credentials=True — browsers '
                "reject that combination outright, and this app relies on credentialed "
                "cross-origin requests (the frontend calling the API from a different "
                "port/origin). List the exact origin(s) that should be allowed instead."
            )
        return self

    @model_validator(mode="after")
    def _check_oidc_issuer(self) -> "Settings":
        """`dex/config.yaml`'s dev provider is deliberately http:// and its
        client secret is public in that file's comments — fine on a
        loopback docker-compose network, not fine anywhere an id_token
        could cross a real network in cleartext. Only enforced in
        production, same as the SECRET_KEY check: nothing here should stop
        `docker compose --profile sso up` from working locally."""
        if (
            self.ENVIRONMENT == "production"
            and self.OIDC_ISSUER
            and not self.OIDC_ISSUER.startswith("https://")
        ):
            raise ValueError(
                f"OIDC_ISSUER='{self.OIDC_ISSUER}' is not https:// while ENVIRONMENT=production. "
                "An OIDC exchange over plain HTTP puts the id_token and access_token on the "
                "wire in cleartext. If this really is a loopback-only identity provider, keep "
                "ENVIRONMENT=development; otherwise put it behind TLS."
            )
        return self


settings = Settings()
