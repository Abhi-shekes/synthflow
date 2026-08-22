from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.template import ProjectTemplate
from app.services.profiling.profile import ProfileError, profile_files

router = APIRouter(prefix="/profile", tags=["profiling"])


class ColumnReport(BaseModel):
    """What was learned about one column, so the UI can show the reasoning
    rather than just the resulting formula."""

    entity: str
    column: str
    field: str
    type: str
    rows: int
    missing: int
    distinct: int
    distribution: str | None = None
    fit_quality: str | None = None
    categories: int | None = None


class ProfileResponse(BaseModel):
    """Same shape as schema import: a template plus what couldn't be
    carried across. Nothing is created until the template is applied via
    `POST /projects/import` — see app.services.schema_import.common for
    why that split is structural rather than a UI convention."""

    template: ProjectTemplate
    warnings: list[str] = Field(default_factory=list)
    report: list[ColumnReport] = Field(default_factory=list)


@router.post("", response_model=ProfileResponse)
async def profile_sample(
    files: list[UploadFile] = File(...),
    project_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    """Learn a project from one or more sample files.

    Multiple files are profiled together on purpose: that's what makes
    detecting relationships between them possible, which a
    one-file-at-a-time endpoint couldn't do.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload at least one file"
        )

    payloads = [(f.filename or "sample.csv", await f.read()) for f in files]

    try:
        result, profiles_by_entity = profile_files(
            payloads,
            max_rows=settings.MAX_PROFILE_ROWS,
            project_name=project_name,
        )
    except ProfileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    report: list[ColumnReport] = []
    for entity in result.template.entities:
        fields_by_name = {f.name: f for f in entity.fields}
        for profile in profiles_by_entity[entity.name]:
            field = fields_by_name.get(profile.field_name)
            report.append(
                ColumnReport(
                    entity=entity.name,
                    column=profile.name,
                    field=profile.field_name,
                    type=profile.inferred_type,
                    rows=profile.total,
                    missing=profile.missing,
                    distinct=profile.distinct,
                    distribution=(field.formula if field is not None else None)
                    or (profile.fit.kind if profile.fit else None),
                    fit_quality=profile.fit.quality if profile.fit else None,
                    categories=len(profile.categories) if profile.categories else None,
                )
            )

    return ProfileResponse(template=result.template, warnings=result.warnings, report=report)
