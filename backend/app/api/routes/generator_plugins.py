from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.plugins import list_available_presets

router = APIRouter(prefix="/generator-plugins", tags=["generator-plugins"])


class GeneratorPresetSummary(BaseModel):
    name: str
    source: str
    category: str


@router.get("", response_model=list[GeneratorPresetSummary])
def list_generator_plugins(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Every preset name a STRING field's `preset` can currently be set to
    — built-in (log/identifier) plus whatever third-party generator
    plugins are installed (see app.services.plugins). The frontend uses
    this instead of a hardcoded list so a newly `pip install`ed plugin
    shows up in the picker without a frontend rebuild."""
    return list_available_presets()
