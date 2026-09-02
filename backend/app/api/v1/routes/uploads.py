"""
Upload route handlers.

Thin HTTP boundary for the upload API:
- POST /uploads (multipart file, optional Idempotency-Key header)
- GET /uploads/{uploadId} (owner or admin)
- DELETE /uploads/{uploadId} (owner or admin, soft-delete)

The routes contain NO domain logic: hashing, MIME/magic validation,
storage I/O, deduplication, and the upload state machine all live in
UploadService and below. This layer parses the request, enforces
authentication/ownership, delegates, and maps results + service
errors to HTTP responses.

Error mapping (08-Security-Architecture §6):
- Missing file part / filename          → 400
- Declared MIME outside the allow-list  → 415 Unsupported Media Type
- Magic-byte mismatch / truncated /
  non-text content                      → 422 validation failure
- Oversized stream                      → 413 Payload Too Large
- Object storage failure                → 502 (generic message, no
  internal detail)
- Non-owner access                      → 404 (enumeration prevention,
  consistent with the user routes)

Traces to: 22-Engineering-Backlog E5.T6 (Upload Route Handlers)
Traces to: 05-API-Specification §6.7-6.8 (contract, divergences noted)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  # runtime: FastAPI path params

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status

from app.api.v1.dependencies.auth import get_current_user, require_role
from app.application.services.upload_service import FileTooLargeError
from app.core.dependencies import get_upload_repository, get_upload_service
from app.domain.entities.upload import Upload  # noqa: TC001
from app.domain.entities.user import User  # noqa: TC001
from app.domain.exceptions import NotFound, StorageError
from app.schemas.auth import PaginationInfo
from app.schemas.upload import UploadListResponse, UploadResponse
from app.utils.file_validation import FileValidationError, MimeTypeNotAllowedError


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.services.upload_service import UploadService
    from app.domain.repositories.upload import UploadRepository


router = APIRouter(tags=["uploads"])

# Multipart read chunk size — keeps request handling streaming-friendly;
# the service and storage adapter keep their own bounded buffering.
_READ_CHUNK = 256 * 1024


async def _file_stream(file: UploadFile) -> AsyncIterator[bytes]:
    """Stream an UploadFile in bounded chunks (never whole-file reads)."""
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            return
        yield chunk


def _to_response(upload: Upload) -> UploadResponse:
    """Map an Upload domain entity to the API response schema."""
    return UploadResponse(
        upload_id=upload.id,
        user_id=upload.user_id,
        original_filename=upload.original_filename,
        content_type=upload.content_type,
        file_size_bytes=upload.file_size_bytes,
        upload_status=upload.upload_status,
        checksum_sha256=upload.checksum_sha256,
        digital_asset_id=upload.digital_asset_id,
        completed_at=upload.completed_at,
        created_at=upload.created_at,
        updated_at=upload.updated_at,
    )


@router.get(
    "",
    response_model=UploadListResponse,
    status_code=status.HTTP_200_OK,
    summary="List uploads for the current user",
    description="Return the authenticated user's paginated upload history.",
)
async def list_uploads(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),  # noqa: B008
    upload_repo: UploadRepository = Depends(get_upload_repository),  # noqa: B008
) -> UploadListResponse:
    """Return the current user's uploads in reverse chronological order."""
    uploaded_items, total = await upload_repo.list_by_user(
        current_user.id,
        skip=offset,
        limit=limit,
        sort_by="created_at",
        sort_order="desc",
    )
    return UploadListResponse(
        items=[_to_response(upload) for upload in uploaded_items],
        pagination_info=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
        ),
    )


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file (analyst/admin)",
    description=(
        "Upload a file as multipart/form-data. The file's bytes are "
        "streamed to object storage while the server computes the "
        "authoritative SHA-256; the declared MIME type is allow-listed "
        "and the actual content's magic bytes are verified (fail "
        "closed). An optional Idempotency-Key header makes retries "
        "safe: the same key returns the original upload."
    ),
)
async def create_upload(
    file: UploadFile = File(...),  # noqa: B008
    idempotency_key: str | None = Header(
        None, alias="Idempotency-Key", max_length=255
    ),
    current_user: User = Depends(require_role(["admin", "analyst"])),  # noqa: B008
    upload_service: UploadService = Depends(get_upload_service),  # noqa: B008
) -> UploadResponse:
    """Ingest a new file and return the resulting upload.

    RBAC: analyst or admin (viewers cannot upload).
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file part with a filename is required",
        )

    try:
        upload = await upload_service.process_upload(
            user_id=current_user.id,
            original_filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            stream=_file_stream(file),
            idempotency_key=idempotency_key,
        )
    except MimeTypeNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except FileValidationError as exc:
        # Magic-byte mismatch / truncated / non-text content
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="File storage is currently unavailable",
        ) from exc

    return _to_response(upload)


@router.get(
    "/{upload_id}",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Get upload detail (owner or admin)",
    description=(
        "Return the current state of an upload. Owner or admin only; "
        "non-owners get 404 (enumeration prevention)."
    ),
)
async def get_upload(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
    upload_repo: UploadRepository = Depends(get_upload_repository),  # noqa: B008
) -> UploadResponse:
    """Retrieve one upload's detail with ownership enforcement."""
    try:
        upload = await upload_repo.get_by_id(upload_id)
    except NotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        ) from exc

    is_admin = current_user.role.value == "admin"
    if not (is_admin or upload.user_id == current_user.id):
        # 404 (not 403) to prevent enumeration, consistent with the
        # user routes.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    return _to_response(upload)


@router.delete(
    "/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete upload (owner or admin, soft-delete)",
    description=(
        "Soft-delete an upload record (the underlying DigitalAsset is "
        "preserved if other uploads reference it, per the safe-deletion "
        "rules). Owner or admin only; non-owners get 404."
    ),
)
async def delete_upload(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
    upload_repo: UploadRepository = Depends(get_upload_repository),  # noqa: B008
) -> None:
    """Soft-delete an upload with ownership enforcement."""
    try:
        upload = await upload_repo.get_by_id(upload_id)
    except NotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        ) from exc

    is_admin = current_user.role.value == "admin"
    if not (is_admin or upload.user_id == current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    await upload_repo.delete(upload_id)
