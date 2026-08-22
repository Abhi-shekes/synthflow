import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.secrets import EncryptedString
from app.db.base import Base


class DatabaseDialect(enum.StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"  # modeled for forward-compat; pushing to it isn't implemented yet


class DatabaseConnection(Base):
    """A user-configured external database SynthFlow can write generated rows
    into (see app.services.db_output).

    The password is encrypted at rest (Phase 10) with a key derived from
    SECRET_KEY — see app.core.secrets for the scheme and, importantly, what
    it does and does not protect against. It is plain `str` in Python; the
    encryption happens in the column type, so there is no way to write this
    column without it. Still never returned by the read API (see
    DatabaseConnectionRead), and a low-privilege database user is still the
    right thing to point at an external system.
    """

    __tablename__ = "database_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dialect: Mapped[DatabaseDialect] = mapped_column(Enum(DatabaseDialect), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
