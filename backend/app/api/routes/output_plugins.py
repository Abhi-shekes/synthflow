from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.plugins import list_available_output_plugins

router = APIRouter(prefix="/output-plugins", tags=["output-plugins"])


class OutputPluginSummary(BaseModel):
    name: str
    source: str


@router.get("", response_model=list[OutputPluginSummary])
def list_output_plugins(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Every plugin_name currently usable on a PluginOutput — see
    app.services.plugins. Mirrors GET /generator-plugins and
    GET /rule-functions for the same reason: the frontend shows this
    instead of hardcoding names, since a plugin's name isn't known until
    it's installed."""
    return list_available_output_plugins()
