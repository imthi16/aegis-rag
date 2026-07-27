"""Document routes (CLAUDE.md §7 Documents). RBAC-filtered.

POST   /documents              upload + ingest (analyst, admin)
GET    /documents              list visible docs (any)
GET    /documents/{id}         detail if visible (any)
DELETE /documents/{id}         delete + FAISS removal + BM25 rebuild (admin)
POST   /documents/{id}/reindex rebuild indexes (admin)
"""

from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit
from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db, require_roles
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.db.models.document import Document
from app.db.models.user import User
from app.ingestion.pipeline import (
    document_faiss_ids,
    ingest_document,
    rebuild_bm25_from_db,
)
from app.ingestion.pipeline import reindex_document as reindex_doc
from app.rbac.classifications import Classification, Role
from app.rbac.enforcement import (
    allowed_document_ids,
    is_document_visible,
    unassignable_roles,
    user_role_set,
)
from app.retrieval.faiss_store import get_faiss_store
from app.schemas.document import (
    DeleteResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentSummary,
    ReindexResponse,
    UploadResponse,
)
from app.schemas.pagination import Pagination, pagination_params

router = APIRouter(prefix="/documents", tags=["documents"])

logger = get_logger("app.documents")


def _ctx(request: Request) -> tuple[str | None, str]:
    ip = request.client.host if request.client else None
    return ip, str(request.state.request_id)


def _write_original(path: str, data: bytes) -> None:
    """Persist an uploaded original to the retained-documents volume."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _summary(doc: Document) -> DocumentSummary:
    return DocumentSummary(
        id=doc.id,
        filename=doc.filename,
        classification=doc.classification,
        allowed_roles=list(doc.allowed_roles),
        chunk_count=doc.chunk_count,
        status=doc.status,
        page_count=doc.page_count,
        created_at=doc.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UploadResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    classification: str = Form(...),
    allowed_roles: list[str] = Form(...),
    user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    settings = get_settings()
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_file_types_list:
        raise ValidationAppError(f"Unsupported file type: {ext or 'unknown'}")

    data = await file.read()
    if len(data) > settings.upload_max_size_mb * 1024 * 1024:
        raise ValidationAppError("File exceeds the maximum upload size.")

    try:
        classification_enum = Classification(classification)
    except ValueError as exc:
        raise ValidationAppError("Invalid classification.") from exc
    try:
        roles = [Role(r) for r in allowed_roles]
    except ValueError as exc:
        raise ValidationAppError("Invalid allowed role.") from exc

    # §6.18: an uploader may only grant roles within its own authority. Enforced
    # here (not just in the UI) so the API cannot be used to widen a document's
    # audience beyond the uploader's own access.
    forbidden = unassignable_roles(user, roles)
    if forbidden:
        raise ForbiddenError(
            "You may not grant access to roles you do not hold: "
            + ", ".join(sorted(r.value for r in forbidden))
        )

    # Retain the original so the document can be re-parsed and re-embedded later
    # (POST /documents/{id}/reindex). Stays inside the perimeter.
    path = os.path.join(settings.document_storage_path, f"{uuid.uuid4()}.{ext}")
    try:
        # Off the event loop: writing up to UPLOAD_MAX_SIZE_MB is blocking I/O.
        await asyncio.to_thread(_write_original, path, data)
        doc = await ingest_document(
            db,
            file_path=path,
            filename=filename,
            filetype=ext,
            classification=classification_enum,
            allowed_roles=roles,
            uploaded_by=user.id,
        )
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise

    # Deduped against an existing document → our freshly stored copy is
    # redundant (the original upload's copy is the one on record).
    if doc.source_path != path and os.path.exists(path):
        os.remove(path)

    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        classification=doc.classification,
        allowed_roles=list(doc.allowed_roles),
        chunk_count=doc.chunk_count,
        status=doc.status,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    classification: str | None = None,
    pg: Pagination = Depends(pagination_params),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    allowed = await allowed_document_ids(db, user)
    if not allowed:
        return DocumentListResponse(items=[], total=0, page=pg.page, size=pg.size)

    conditions: list[ColumnElement[bool]] = [Document.id.in_(allowed)]
    if classification:
        conditions.append(Document.classification == classification)

    total = (
        await db.execute(select(func.count()).select_from(Document).where(*conditions))
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(Document)
                .where(*conditions)
                .order_by(Document.created_at.desc())
                .offset(pg.offset)
                .limit(pg.size)
            )
        )
        .scalars()
        .all()
    )
    return DocumentListResponse(
        items=[_summary(d) for d in rows], total=total, page=pg.page, size=pg.size
    )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetail:
    doc = await db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    if not is_document_visible(doc, user_role_set(user)):
        raise ForbiddenError("You do not have access to this document.")
    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        classification=doc.classification,
        allowed_roles=list(doc.allowed_roles),
        chunk_count=doc.chunk_count,
        status=doc.status,
        page_count=doc.page_count,
        created_at=doc.created_at,
        content_hash=doc.content_hash,
        filetype=doc.filetype,
        uploaded_by=doc.uploaded_by,
        metadata=dict(doc.doc_metadata),
    )


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_roles(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
    doc = await db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")

    faiss_ids = await document_faiss_ids(db, doc.id)
    source_path = doc.source_path
    ip, rid = _ctx(request)
    await db.delete(doc)  # cascade removes chunks
    await write_audit(
        db,
        actor_id=user.id,
        actor_roles=user.role_names,
        action="document.deleted",
        resource_type="document",
        resource_id=str(document_id),
        outcome="success",
        ip=ip,
        request_id=rid,
        details={"filename": doc.filename, "chunk_count": len(faiss_ids)},
    )
    await db.commit()

    # Post-commit asset cleanup: drop vectors, rebuild lexical index, and remove
    # the retained original so a delete leaves no content behind.
    store = get_faiss_store()
    if faiss_ids:
        store.remove(faiss_ids)
        store.save()
    await rebuild_bm25_from_db(db)
    if source_path and os.path.exists(source_path):
        try:
            os.remove(source_path)
        except OSError:
            logger.warning("stored_original_unlink_failed", document_id=str(document_id))
    return DeleteResponse()


@router.post(
    "/{document_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReindexResponse,
)
async def reindex_document(
    document_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_roles(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ReindexResponse:
    doc = await db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")

    # Full rebuild of both channels: re-parse the stored original, re-chunk,
    # re-embed into FAISS, swap the chunk rows, rebuild BM25.
    try:
        chunk_count = await reindex_doc(db, doc)
    except FileNotFoundError as exc:
        raise ValidationAppError(
            "The stored original for this document is unavailable, so it cannot "
            "be reindexed. Re-upload the document instead."
        ) from exc

    ip, rid = _ctx(request)
    await write_audit(
        db,
        actor_id=user.id,
        actor_roles=user.role_names,
        action="document.reindexed",
        resource_type="document",
        resource_id=str(document_id),
        outcome="success",
        ip=ip,
        request_id=rid,
        details={"filename": doc.filename, "chunk_count": chunk_count},
    )
    await db.commit()
    return ReindexResponse()
