from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.services.expressions import BUILTIN_FUNCTIONS
from app.services.plugins import list_available_rule_functions

router = APIRouter(prefix="/rule-functions", tags=["rule-functions"])


class RuleFunctionSummary(BaseModel):
    name: str
    source: str


@router.get("", response_model=list[RuleFunctionSummary])
def list_rule_functions(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Every function name currently callable from a rule/event-trigger
    condition or a formula (app.services.expressions.evaluate) — the
    built-ins plus whatever rule-function plugins are installed. Mirrors
    GET /generator-plugins for the same reason: the frontend shows this
    instead of hardcoding function names."""
    functions = [{"name": name, "source": "builtin"} for name in BUILTIN_FUNCTIONS]
    functions += list_available_rule_functions()
    return functions
