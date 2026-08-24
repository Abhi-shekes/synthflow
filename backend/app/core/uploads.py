"""Bounds on reading an uploaded file into memory.

`UploadFile.read()` with no argument reads the whole body into one `bytes`
object, whatever its size — there's nothing in FastAPI/Starlette that caps
that for you. `app.services.ingest.fetch_url` already had to solve this for
a URL fetch: read one byte past the limit and reject, rather than trusting
a declared size, because a sender can lie about or omit it. Every route
that accepts a file upload should read it through `read_capped` for the
same reason: a multi-gigabyte multipart body is a memory-exhaustion DoS
available to anyone who can authenticate, which for this app means anyone
who can sign up.
"""

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


async def read_capped(file: UploadFile, max_bytes: int | None = None) -> bytes:
    limit = settings.MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That file is over the {limit // (1024 * 1024)} MB upload limit",
        )
    return content
