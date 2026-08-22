import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ActorKind(enum.StrEnum):
    """How the caller proved who they were.

    Worth recording separately from the user, because the answer to "did I
    do that or did my CI pipeline" is the first question anyone asks of an
    audit log, and both arrive as the same user.
    """

    SESSION = "session"
    API_KEY = "api_key"


class AuditEvent(Base):
    """One thing that changed, and who changed it.

    **Recorded by middleware over every mutating request, not by calls
    sprinkled through the routes.** An audit log assembled by remembering to
    log is an audit log with holes in it, and the holes are invisible: the
    entry that is missing looks exactly like the thing that never happened.
    Deriving it from the request means a route added tomorrow is covered
    without anyone thinking about it — the same argument that made the
    read-only API key scope a method check rather than an endpoint list.

    The cost is that entries describe requests rather than intentions:
    `POST /projects/{id}/entities` rather than "added an entity". The route
    template and its path parameters carry enough to answer the questions
    the roadmap asked — who changed a schema, ran a generation, pushed to a
    database — and a hand-written description per route would drift from
    what the route actually does.

    **Only mutating requests are recorded.** A read-heavy API would
    otherwise turn every GET into a write, and "who looked at this" is a
    different feature with a different cost profile. Failed requests are
    kept: an authorisation failure is exactly the thing an audit log exists
    to show.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Nullable so deleting a user does not delete the record of what they
    # did. `ondelete="SET NULL"` rather than CASCADE for the same reason.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Denormalised on purpose: after the user row is gone, "who" has to
    # still be answerable, and a foreign key alone cannot answer it.
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    actor_kind: Mapped[ActorKind] = mapped_column(Enum(ActorKind), nullable=False)
    # Which key, when it was a key. Also denormalised, since a revoked key
    # can be deleted and the event must still name it.
    api_key_prefix: Mapped[str | None] = mapped_column(String(32), nullable=True)

    method: Mapped[str] = mapped_column(String(10), nullable=False)
    # The route *template* (`/projects/{project_id}/entities`), not the
    # concrete path. Templates are a small set, so they group and filter;
    # concrete paths are unbounded and group into nothing.
    #
    # The `/api/v1` prefix is deliberately absent: it is the router-relative
    # template, so a future version bump does not split one route's history
    # into two unrelated-looking halves. Every route in this application
    # shares the one prefix, so nothing is ambiguous without it.
    route: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)

    # Pulled out of the path so "everything that happened to this project"
    # is an indexed query rather than a scan with string matching.
    project_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    # The rest of the path parameters. JSON rather than columns because the
    # set differs per route and inventing a column per id would mean a
    # migration every time a route gains one.
    path_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped["User | None"] = relationship()
