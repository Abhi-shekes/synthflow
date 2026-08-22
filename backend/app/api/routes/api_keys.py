import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_session
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services import api_keys

# Every route here requires a *session*, not just a caller. See
# `deps.require_session`: a key that can mint keys outlives its own
# revocation.
router = APIRouter(prefix="/api-keys", tags=["api keys"])


@router.get("", response_model=list[ApiKeyRead])
def list_api_keys(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[ApiKey]:
    """Every key this user has, revoked ones included, newest first.

    Revoked keys stay in the list rather than disappearing: "this key was
    revoked last Tuesday" is the answer someone investigating an incident
    needs, and a list that silently drops them cannot give it.

    Which is exactly why it is paged. Keeping every key forever means the
    list only grows, so "all of them" stops being a sensible response for an
    account that has been rotating keys for a year.
    """
    return list(
        db.scalars(
            select(ApiKey)
            .where(ApiKey.user_id == current_user.id)
            # `id` breaks the tie. `created_at` comes from the database
            # clock, so keys minted in one burst share it to the microsecond
            # and ordering by it alone is unstable — which means paging can
            # repeat one key and skip another. In ordinary use keys are made
            # minutes apart and this never shows; a script creating a dozen
            # at once is exactly when it does.
            .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(require_session),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    """Mint a key. **The secret is in this response and nowhere else** —
    it is not stored in a form that can be read back, so a caller that loses
    it makes a new key."""
    try:
        api_key, secret = api_keys.generate(
            db,
            current_user.id,
            name=payload.name,
            scope=payload.scope,
            expires_at=payload.expires_at,
        )
    except api_keys.ApiKeyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    db.refresh(api_key)
    return ApiKeyCreated(**ApiKeyRead.model_validate(api_key).model_dump(), key=secret)


@router.delete("/{key_id}", response_model=ApiKeyRead)
def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(require_session),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Revoke a key, keeping the row.

    Returns the key rather than 204 so the caller can see the revocation
    timestamp it just caused. Revoking an already-revoked key is a no-op
    with the original timestamp intact — the caller wanted it dead, and it
    is, and moving the timestamp would rewrite when it actually happened.
    """
    api_key = db.get(ApiKey, key_id)
    if api_key is None or api_key.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_keys.revoke(db, api_key)
    db.refresh(api_key)
    return api_key
