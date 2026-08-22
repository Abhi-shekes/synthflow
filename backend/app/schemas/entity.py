import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.error_injection import ErrorInjectionRead
from app.schemas.event_trigger import EventTriggerRead
from app.schemas.field import EntityFieldRead
from app.schemas.geo_route import GeoRouteRead
from app.schemas.lookup_attachment import LookupAttachmentRead
from app.schemas.rule import RuleRead
from app.schemas.trend import TrendRead
from app.schemas.workflow import WorkflowRead


class EntityCreate(BaseModel):
    name: str


class EntityUpdate(BaseModel):
    name: str | None = None


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    fields: list[EntityFieldRead] = []
    rules: list[RuleRead] = []
    event_triggers: list[EventTriggerRead] = []
    workflows: list[WorkflowRead] = []
    trends: list[TrendRead] = []
    error_injections: list[ErrorInjectionRead] = []
    lookup_attachments: list[LookupAttachmentRead] = []
    geo_routes: list[GeoRouteRead] = []


class GenerateRequest(BaseModel):
    count: int = 10


class PrivacyReportRequest(BaseModel):
    """Which columns an attacker is assumed to already know, and what they
    must not learn.

    Both are judgement calls about the threat model, not properties of the
    data, so they are asked for rather than guessed. Defaults mirror
    app.services.privacy.anonymity.DEFAULT_K / DEFAULT_L — 5 is the common
    regulatory floor, not a law.
    """

    count: int = 1000
    quasi_identifiers: list[str]
    sensitive_field: str | None = None
    k_threshold: int = 5
    l_threshold: int = 2
