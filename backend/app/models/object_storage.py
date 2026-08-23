import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.secrets import EncryptedString
from app.db.base import Base


class StorageProvider(enum.StrEnum):
    """Which object-storage API to speak.

    Only one entry, and that is the point rather than an omission: AWS S3's
    API is a de-facto standard, and MinIO, Cloudflare R2, Backblaze B2 and
    DigitalOcean Spaces all implement it. Targeting the API with a
    configurable `endpoint_url` covers every one of them with a single
    connector, where naming each vendor would have produced five
    near-identical ones.

    Google Cloud Storage and Azure Blob are deliberately absent.
    GCS can be reached today through its
    S3-interoperability endpoint; Azure cannot, and needs its own SDK.
    """

    S3 = "s3"


class ObjectStorageTarget(Base):
    """A bucket generated files can be uploaded to.

    Deliberately shaped like `DatabaseConnection` — project-scoped, named,
    with credentials that are never returned by the read API and a secret
    encrypted at rest through the same column type Phase 10 introduced.
    A second, differently-shaped way to hold credentials would be a second
    thing to get wrong.

    This is a destination for *artifacts*, not a streaming output. A
    generation job writes its file locally and then uploads it, which is
    why it hangs off `GenerationJob` rather than joining the row-oriented
    outputs (Kafka, MQTT, REST, plugins).
    """

    __tablename__ = "object_storage_targets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[StorageProvider] = mapped_column(
        Enum(StorageProvider), nullable=False, default=StorageProvider.S3
    )
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    # Optional key prefix, so one bucket can hold several projects without
    # them colliding. Stored without a trailing slash; see object_storage.
    prefix: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="us-east-1")
    # Empty means "real AWS". Anything else is MinIO, R2, Spaces, B2 or
    # another S3-compatible server.
    endpoint_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_access_key: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
