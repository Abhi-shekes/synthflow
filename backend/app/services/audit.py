"""Recording who changed what.

The whole design is one decision: **the log is derived from the request, not
written by the routes.** An audit log assembled by remembering to call
`log()` is an audit log with holes in it, and the holes are invisible — the
entry that is missing looks exactly like the thing that never happened. A
route added tomorrow is covered without anyone thinking about it.

What that costs is precision of language: entries say
`POST /projects/{id}/entities` rather than "added an entity". The route
template and its path parameters answer the questions the roadmap asked, and
a hand-written description per route would drift from what the route does.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import ActorKind, AuditEvent

# GET and HEAD change nothing, and recording them would turn every read into
# a write. "Who looked at this" is a different feature with a different cost
# profile, and pretending this one provides it would be worse than not
# having it.
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def record(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    actor_email: str | None,
    actor_kind: ActorKind,
    api_key_prefix: str | None,
    method: str,
    route: str,
    status_code: int,
    path_params: dict[str, Any],
) -> AuditEvent:
    """Write one entry. Committed by the caller."""
    params = {k: str(v) for k, v in path_params.items()}
    event = AuditEvent(
        user_id=user_id,
        actor_email=actor_email,
        actor_kind=actor_kind,
        api_key_prefix=api_key_prefix,
        method=method,
        route=route,
        status_code=status_code,
        project_id=_uuid_or_none(params.get("project_id")),
        path_params=params,
    )
    db.add(event)
    return event


def read(
    db: Session,
    user_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEvent]:
    """Newest-first entries the caller is allowed to see.

    Two different scopes, chosen by whether `project_id` is given:

    * No project: "everything I did" — there is no other honest global
      answer. Every project this user can reach might be shared with
      people they don't otherwise know are on it, so a global feed of
      *everyone's* activity across all of them would leak more than "my
      own history" implies.
    * A project: every actor's entries on *that* project, not just the
      caller's. The route (`app.api.routes.audit`) checks the caller can
      see the project before calling this — once that's established,
      "who did what to this project" is exactly what a shared project's
      audit trail is for, and filtering it down to one member's own
      actions would hide the rest of the team's changes from each other.

    `id` breaks the `created_at` tie — the database clock is shared by
    everything written in one instant, and an unstable order means paging
    both repeats and skips.
    """
    if project_id is not None:
        query = select(AuditEvent).where(AuditEvent.project_id == project_id)
    else:
        query = select(AuditEvent).where(AuditEvent.user_id == user_id)
    return list(
        db.scalars(
            query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
