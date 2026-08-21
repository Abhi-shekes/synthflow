import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.entities import _get_owned_entity
from app.db.session import get_db
from app.models.plugin_output import PluginOutput
from app.models.user import User
from app.schemas.plugin_output import PluginOutputCreate, PluginOutputRead
from app.services.plugin_output_producers import start_plugin_output, stop_plugin_output
from app.services.plugins import available_output_plugins

router = APIRouter(
    prefix="/projects/{project_id}/entities/{entity_id}/plugin-outputs", tags=["plugin-outputs"]
)


@router.get("", response_model=list[PluginOutputRead])
def list_plugin_outputs(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PluginOutput]:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    return db.query(PluginOutput).filter(PluginOutput.entity_id == entity.id).all()


@router.post("", response_model=PluginOutputRead, status_code=status.HTTP_201_CREATED)
async def create_plugin_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload: PluginOutputCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PluginOutput:
    entity = _get_owned_entity(project_id, entity_id, current_user, db)
    if not entity.fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Entity has no fields to generate"
        )
    if payload.plugin_name not in available_output_plugins():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown output plugin '{payload.plugin_name}'",
        )
    output = PluginOutput(entity_id=entity_id, **payload.model_dump())
    db.add(output)
    db.commit()
    db.refresh(output)
    start_plugin_output(output)
    return output


@router.delete("/{plugin_output_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin_output(
    project_id: uuid.UUID,
    entity_id: uuid.UUID,
    plugin_output_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_entity(project_id, entity_id, current_user, db)
    output = db.get(PluginOutput, plugin_output_id)
    if output is None or output.entity_id != entity_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin output not found")
    stop_plugin_output(output.id)
    db.delete(output)
    db.commit()
