"""The retrieval-augmented generation pipeline, end to end.

    ingest:   resume text -> chunks -> embeddings -> stored vectors
    retrieve: job description -> query vector -> nearest chunks
    answer:   nearest chunks -> grounded, cited suggestions
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentChunk
from app.rag import store
from app.rag.chunker import chunk_resume
from app.rag.embeddings import get_embedder
from app.rag.generation import get_generator

# Retrieving more than this stops helping: the later passages are weak matches
# and mostly serve to dilute the prompt and raise token cost.
MAX_TOP_K = 20
DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class Answer:
    """A generated answer and the passages it was grounded in."""

    answer: str
    sources: list[store.ScoredChunk]


async def ingest_resume(
    db: AsyncSession, user_id: uuid.UUID, document_name: str, text: str
) -> int:
    """Chunk, embed and store a resume. Returns the number of chunks stored.

    Re-ingesting the same document name replaces its chunks rather than adding
    a second copy. Without this, editing a resume and re-uploading would leave
    the old bullets in the index competing with the new ones.
    """
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.user_id == user_id,
            DocumentChunk.document_name == document_name,
        )
    )

    chunks = chunk_resume(text)
    if not chunks:
        await db.commit()
        return 0

    vectors = get_embedder().embed([chunk.embedding_text for chunk in chunks])

    db.add_all(
        [
            DocumentChunk(
                user_id=user_id,
                document_name=document_name,
                section=chunk.section,
                text=chunk.text,
                ordinal=chunk.ordinal,
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors)
        ]
    )
    await db.commit()
    return len(chunks)


async def retrieve(
    db: AsyncSession, user_id: uuid.UUID, query: str, k: int = DEFAULT_TOP_K
) -> list[store.ScoredChunk]:
    """Return the user's passages most relevant to `query`, best first."""
    k = max(1, min(k, MAX_TOP_K))
    query_vector = get_embedder().embed([query])[0]
    return await store.search(db, user_id, query_vector, k)


async def answer_for_job(
    db: AsyncSession, user_id: uuid.UUID, job_description: str, k: int = DEFAULT_TOP_K
) -> Answer:
    """Retrieve, then generate tailoring suggestions grounded in what was found."""
    chunks = await retrieve(db, user_id, job_description, k)
    text = get_generator().generate(job_description, chunks)
    return Answer(answer=text, sources=chunks)
