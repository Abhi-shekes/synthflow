import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DatabaseDialect(enum.StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"  # modeled for forward-compat; pushing to it isn't implemented yet


class DatabaseConnection(Base):
    """A user-configured external database SynthFlow can write generated rows
    into (see app.services.db_output).

    The password is stored in plaintext — this repo has no secret
    encryption-at-rest yet. Use a low-privilege database user for this, the
    same way you would for any external tool pointed at a database from
    outside it. Never returned by the read API (see DatabaseConnectionRead).
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
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
