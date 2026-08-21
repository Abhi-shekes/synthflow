import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.error_injection import ErrorInjection
    from app.models.event_trigger import EventTrigger
    from app.models.field import EntityField
    from app.models.lookup_attachment import LookupAttachment
    from app.models.project import Project
    from app.models.rule import Rule
    from app.models.trend import Trend
    from app.models.workflow import Workflow


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="entities")
    fields: Mapped[list["EntityField"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", order_by="EntityField.order"
    )
    rules: Mapped[list["Rule"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", order_by="Rule.created_at"
    )
    event_triggers: Mapped[list["EventTrigger"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", order_by="EventTrigger.created_at"
    )
    workflows: Mapped[list["Workflow"]] = relationship(
        cascade="all, delete-orphan", order_by="Workflow.created_at"
    )
    trends: Mapped[list["Trend"]] = relationship(
        cascade="all, delete-orphan", order_by="Trend.created_at"
    )
    error_injections: Mapped[list["ErrorInjection"]] = relationship(
        cascade="all, delete-orphan", order_by="ErrorInjection.created_at"
    )
    lookup_attachments: Mapped[list["LookupAttachment"]] = relationship(
        cascade="all, delete-orphan", order_by="LookupAttachment.created_at"
    )
