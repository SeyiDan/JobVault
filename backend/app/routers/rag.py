"""Endpoints for indexing a resume and querying it against a job description.

Both routes sit behind `get_current_user`, the same dependency the jobs router
uses, and every query is scoped to the caller's own chunks inside the SQL. A
resume is the most personal document in this application; retrieval that could
cross users would leak one person's employment history into another person's
suggestions.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.rag import pipeline
from app.schemas import (
    RagQueryRequest,
    RagQueryResponse,
    ResumeIngestRequest,
    ResumeIngestResponse,
    RetrievedChunk,
)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/documents", response_model=ResumeIngestResponse)
async def ingest_document(
    payload: ResumeIngestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Chunk, embed and index a resume for the current user.

    Re-posting the same `document_name` replaces that document's chunks, so
    editing and re-uploading a resume does not leave stale bullets in the index.
    """
    count = await pipeline.ingest_resume(
        db, user.id, payload.document_name, payload.text
    )
    return ResumeIngestResponse(
        document_name=payload.document_name, chunks_indexed=count
    )


@router.post("/query", response_model=RagQueryResponse)
async def query(
    payload: RagQueryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the resume passages relevant to a job description, and use them
    to generate tailoring suggestions that cite the passage each came from."""
    result = await pipeline.answer_for_job(
        db, user.id, payload.job_description, payload.top_k
    )
    return RagQueryResponse(
        answer=result.answer,
        sources=[
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                section=chunk.section,
                text=chunk.text,
                score=chunk.score,
            )
            for chunk in result.sources
        ],
    )
