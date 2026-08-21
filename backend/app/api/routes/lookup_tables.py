import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.projects import _get_owned_project
from app.core.config import settings
from app.db.session import get_db
from app.models.lookup_table import LookupTable
from app.models.user import User
from app.schemas.lookup_table import LookupTableRead
from app.services.lookup_tables import LookupParseError, parse_upload

router = APIRouter(prefix="/projects/{project_id}/lookup-tables", tags=["lookup-tables"])


@router.get("", response_model=list[LookupTableRead])
def list_lookup_tables(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LookupTable]:
    _get_owned_project(project_id, current_user, db)
    return (
        db.query(LookupTable)
        .filter(LookupTable.project_id == project_id)
        .order_by(LookupTable.created_at)
        .all()
    )


@router.post("", response_model=LookupTableRead, status_code=status.HTTP_201_CREATED)
async def create_lookup_table(
    project_id: uuid.UUID,
    name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LookupTable:
    _get_owned_project(project_id, current_user, db)

    content = await file.read()
    try:
        columns, rows = parse_upload(file.filename or "", content, settings.MAX_LOOKUP_ROWS)
    except LookupParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    lookup_table = LookupTable(
        project_id=project_id,
        name=name,
        columns=columns,
        data=rows,
        row_count=len(rows),
    )
    db.add(lookup_table)
    db.commit()
    db.refresh(lookup_table)
    return lookup_table


@router.delete("/{lookup_table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lookup_table(
    project_id: uuid.UUID,
    lookup_table_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)
    lookup_table = db.get(LookupTable, lookup_table_id)
    if lookup_table is None or lookup_table.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lookup table not found"
        )
    db.delete(lookup_table)
    db.commit()
