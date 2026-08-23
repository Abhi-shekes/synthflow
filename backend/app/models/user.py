import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # "guided" hides Behaviour/Distortion/advanced-Delivery depth by default and
    # is what every new account starts on; "advanced" is the full instrument
    # panel. A plain string column rather than a DB enum — SQLite has no enum
    # type, and Postgres would need a migration to add a third mode later.
    ui_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="guided", server_default="guided")
    # Whether this user has been through (or explicitly skipped) the first-run
    # welcome flow. False only until then, permanently true after — it must
    # never re-trigger uninvited.
    has_onboarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    projects: Mapped[list["Project"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
