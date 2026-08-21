from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.install import describe

router = APIRouter(prefix="/install-config", tags=["install-config"])


class FeatureStatus(BaseModel):
    key: str
    label: str
    description: str
    extra: str
    available: bool


@router.get("", response_model=list[FeatureStatus])
def get_install_config(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    """Which optional capabilities this particular install actually has —
    see app.services.install. The frontend uses this to grey out an output
    it can't offer and explain how to enable it, rather than showing a
    control whose only possible outcome is an error."""
    return describe()
