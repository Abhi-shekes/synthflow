import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.field import EntityField
    from app.models.lookup_table import LookupTable


class GeoRoute(Base):
    """Attaches one OBJECT/JSON field to an ordered sequence of waypoints
    from a project-level LookupTable — a third way of consuming that upload
    (see LookupAttachment for "sample one value" and TimelineReplay for
    "walk in order against a clock"; this is "walk in order across the
    generated batch, interpolated"). The field's value becomes
    `{"lat": float, "lon": float}`, linearly interpolated between the two
    waypoints bounding each row's fractional position within the *current
    batch* (see app.services.geo_routes.generate_geo_point) — the same
    "value is a function of row position within this call" idea as Trend,
    just for a 2D point walking a path instead of a scalar following a
    curve.

    "Stops" (dwelling at a location) aren't a separate configured concept:
    upload the same waypoint more than once in a row in the source data and
    however many output rows land in that now-tiny segment interpolate to
    essentially the same point — a natural consequence of the interpolation,
    not a special case. Speed and traffic aren't built here either: compose
    a plain FLOAT field (optionally with a Trend, or an ErrorInjection
    out_of_range for a "jammed" outlier) the same way latency already does
    for API-behavior simulation — a GeoRoute only owns *where*, not how
    fast.
    """

    __tablename__ = "geo_routes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_fields.id", ondelete="CASCADE"), unique=True
    )
    lookup_table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lookup_tables.id", ondelete="CASCADE")
    )
    lat_column: Mapped[str] = mapped_column(String(255), nullable=False)
    lon_column: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    field: Mapped["EntityField"] = relationship()
    lookup_table: Mapped["LookupTable"] = relationship(back_populates="geo_routes")
