"""Vector search, with a pgvector backend and a portable numpy backend.

The two exist for a concrete reason. Production runs on Postgres, where pgvector
does the nearest-neighbour search inside the database and can use an index, so
the whole corpus never crosses the wire. The test suite runs on SQLite, which
has no pgvector and never will, and the existing suite's speed comes from not
needing a database container.

Rather than let those diverge, both backends implement the same `search` and are
selected from the session's dialect at call time. The numpy backend loads the
user's chunks and ranks them in process, which is correct but O(n) per query;
that is fine for a test fixture and wrong for production, which is exactly why
the pgvector path exists.

Both backends rank by cosine similarity over unit vectors, so their orderings
agree and a test written against one is meaningful for the other.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentChunk


@dataclass(frozen=True)
class ScoredChunk:
    """A retrieved chunk and how well it matched."""

    chunk_id: uuid.UUID
    text: str
    section: str
    score: float


def _cosine(left: list[float], right: list[float]) -> float:
    """Dot product. Both embedders emit unit vectors, so this is the cosine."""
    return sum(a * b for a, b in zip(left, right))


async def _search_numpy(
    db: AsyncSession, user_id: uuid.UUID, query_vector: list[float], k: int
) -> list[ScoredChunk]:
    """Rank in process. Portable to SQLite; O(n) in the user's chunk count."""
    rows = (
        await db.execute(select(DocumentChunk).where(DocumentChunk.user_id == user_id))
    ).scalars().all()

    scored = [
        ScoredChunk(
            chunk_id=row.id,
            text=row.text,
            section=row.section,
            score=_cosine(query_vector, list(row.embedding)),
        )
        for row in rows
        # A chunk written by a different embedding backend is not comparable to
        # this query vector. Skip it rather than return a meaningless score.
        if row.embedding is not None and len(row.embedding) == len(query_vector)
    ]
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:k]


async def _search_pgvector(
    db: AsyncSession, user_id: uuid.UUID, query_vector: list[float], k: int
) -> list[ScoredChunk]:
    """Rank inside Postgres with pgvector's cosine distance operator."""
    # `<=>` is cosine DISTANCE, so similarity is 1 - distance. Ordering ascending
    # by distance is the same as descending by similarity.
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    rows = (
        await db.execute(
            select(DocumentChunk, distance.label("distance"))
            .where(DocumentChunk.user_id == user_id)
            .order_by(distance)
            .limit(k)
        )
    ).all()

    return [
        ScoredChunk(
            chunk_id=row.DocumentChunk.id,
            text=row.DocumentChunk.text,
            section=row.DocumentChunk.section,
            score=1.0 - float(row.distance),
        )
        for row in rows
    ]


async def search(
    db: AsyncSession, user_id: uuid.UUID, query_vector: list[float], k: int = 5
) -> list[ScoredChunk]:
    """Return the user's k most similar chunks, best first.

    Scoped to `user_id` in both backends. Retrieval that crossed users would leak
    one person's resume into another person's suggestions, so the filter is part
    of the query rather than something applied afterwards.
    """
    if k <= 0:
        return []
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return await _search_pgvector(db, user_id, query_vector, k)
    return await _search_numpy(db, user_id, query_vector, k)
