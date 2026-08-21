import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entity import Entity


class FieldType(enum.StrEnum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    ENUM = "enum"
    ARRAY = "array"
    OBJECT = "object"
    JSON = "json"


class LogPreset(enum.StrEnum):
    """A canned single-line log/event format for a STRING field — see
    app.services.log_generators for what each one actually produces.
    Covers both the roadmap's "log generators" (real infra formats) and
    "security event generator" (detection-testing formats) items with one
    mechanism, since both are the same shape of problem: realistic-looking
    templated text, not a new generation engine."""

    NGINX_ACCESS_LOG = "nginx_access_log"
    DOCKER_LOG = "docker_log"
    KUBERNETES_EVENT = "kubernetes_event"
    LINUX_SYSLOG = "linux_syslog"
    APPLICATION_LOG = "application_log"
    FAILED_LOGIN = "failed_login"
    BRUTE_FORCE = "brute_force"
    SQLI_ATTEMPT = "sqli_attempt"
    DDOS_ATTEMPT = "ddos_attempt"
    PORT_SCAN = "port_scan"
    MALWARE_ALERT = "malware_alert"


class EntityField(Base):
    __tablename__ = "entity_fields"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[FieldType] = mapped_column(Enum(FieldType), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    required: Mapped[bool] = mapped_column(Boolean, default=False)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    unique: Mapped[bool] = mapped_column(Boolean, default=False)

    default_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    regex: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # When set (STRING fields only, mutually exclusive with regex — see
    # entities._validate_preset), the field's value comes from one of the
    # canned log/event line generators in app.services.log_generators
    # instead of exrex/faker.word(). Stored as a plain string rather than a
    # DB-level Enum column, same choice already made for regex: validated at
    # the schema/route layer, not enforced by the database.
    preset: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Always configured as strings (e.g. "200", not 200), but a value that
    # looks numeric comes out of generation as a real int/float, not a
    # string — see app.services.lookup_tables.coerce_numeric, reused by
    # app.services.generator's ENUM branch. This is what makes a weighted
    # HTTP status code enum ("200"/"404"/"500" + enum_weights) produce real
    # integers for API-behavior-simulation use cases, without a separate
    # "value type" column.
    enum_values: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Optional weights parallel to enum_values (same length, same order) for
    # weighted-random selection instead of uniform random.choice — the
    # "probability engine" from the spec. None means uniform, matching prior
    # behavior; see app.services.generator._generate_value.
    enum_weights: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # When set, this field's value is computed from other fields on the same
    # row (see app.services.expressions) instead of being randomly generated.
    # It must only reference fields with a lower `order` on the same entity —
    # rows are built in order, so later fields can see earlier ones' values.
    formula: Mapped[str | None] = mapped_column(String(500), nullable=True)

    entity: Mapped["Entity"] = relationship(back_populates="fields")
