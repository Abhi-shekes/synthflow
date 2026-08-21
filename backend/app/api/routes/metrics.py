from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

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
