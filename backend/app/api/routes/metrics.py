from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.deps import get_current_user
from app.models.user import User
from app.services import metrics as metrics_service

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics_endpoint() -> Response:
    """Prometheus scrape endpoint.

    Deliberately unauthenticated and outside `/api/v1`, alongside
    `/healthz`: Prometheus scrapes on a fixed interval with no way to
    refresh a JWT, and every practical alternative (a static bearer token
    in the scrape config, a second auth scheme) is worse for no real
    gain here. What makes that safe is the metrics themselves — see
    app.services.metrics on why every label value is drawn from a fixed,
    hardcoded set. Nothing here is labelled by project, entity, field, or
    user, so this exposes throughput/latency/error counts and nothing
    about anyone's schema or data. Same trust model as the existing
    public output routes: don't expose it to the internet unless you mean
    to.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


summary_router = APIRouter(prefix="/metrics", tags=["metrics"])


@summary_router.get("/summary")
def metrics_summary(current_user: User = Depends(get_current_user)) -> dict:
    """The same numbers as `/metrics`, as JSON, behind the session token.

    The in-app live monitor exists because the README promises events/sec,
    active streams and error rates in the product, and until now only
    Grafana had them — which means they were only there for installs that
    turned on the optional `monitoring` Compose profile.

    Three ways to feed a browser dashboard were on the table, and this is
    the least bad:

    - Parse the exposition format in the frontend. Means shipping a
      Prometheus text parser to the client and re-deriving series names
      there, so a metric rename breaks the dashboard silently.
    - Let the app's origin read the unauthenticated `/metrics`. Widens who
      can reach that endpoint from "your monitoring network" to "anything
      that can reach the API", for no gain.
    - This: one authenticated projection, server-side, reading the same
      registry so there is no second source of truth to drift.

    The cost, recorded honestly: two surfaces now render one set of
    numbers, and adding a metric means touching `summary()` as well as
    defining it.

    Not scoped to a project, because the underlying metrics are not — see
    app.services.metrics on why label cardinality is bounded. Any signed-in
    user sees process-wide totals; that is the same information `/metrics`
    already gives anyone who can reach it.
    """
    return metrics_service.summary()
