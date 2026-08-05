"""Tests for the resume retrieval pipeline.

These run with EMBEDDING_BACKEND=hashing, set in conftest.py. The hashing
embedder is deterministic and needs no model download, so the suite stays fast
and offline. It is also a weaker retriever than the real backend, so these tests
deliberately assert on plumbing, ordering and isolation rather than on semantic
quality. Quality is measured separately by eval/run_eval.py, which uses the real
sentence-transformer backend and reports recall@k and MRR.
"""

import pytest
from httpx import AsyncClient

from app.rag.chunker import chunk_resume
from app.rag.embeddings import EMBEDDING_DIM, HashingEmbedder
from app.rag.generation import ExtractiveGenerator, format_context
from app.rag.store import ScoredChunk

RESUME = """\
## Enterprise e-Commerce API

- Query optimization: replaced an N+1 ORM access pattern with parameterized raw
  SQL across three tables, cutting 1,001 queries down to 1.
- Access control: enforced role-based authorization through FastAPI dependency
  injection so privileged routes cannot be reached by an ordinary account.

## IoT Intrusion Detection Research

- Transfer learning: trained five models across three published IoT datasets and
  reached 89.1 percent accuracy at a 3.1 percent false positive rate.

## Microsoft TEALS

- Mentoring: taught Python and Java to 25 high school students through weekly
  code review sessions.
"""


# --- chunker ---


def test_chunker_splits_on_bullets_and_keeps_the_section():
    chunks = chunk_resume(RESUME)

    assert len(chunks) == 4
    sections = {chunk.section for chunk in chunks}
    assert "Enterprise e-Commerce API" in sections
    assert "IoT Intrusion Detection Research" in sections

    # The section heading is prepended for embedding, so a bare metric is not
    # stranded from the project it belongs to.
    query_chunk = next(c for c in chunks if "1,001" in c.text)
    assert query_chunk.embedding_text.startswith("Enterprise e-Commerce API:")


def test_chunker_drops_fragments_too_short_to_be_achievements():
    chunks = chunk_resume("## Skills\n\n- Python\n- 2023\n")
    assert chunks == []


def test_chunker_handles_empty_input():
    assert chunk_resume("") == []


# --- embedder ---


def test_hashing_embedder_is_deterministic_and_unit_length():
    embedder = HashingEmbedder()
    first, second = embedder.embed(["query optimization", "query optimization"])

    assert first == second
    assert len(first) == EMBEDDING_DIM
    assert sum(component * component for component in first) == pytest.approx(1.0)


def test_shared_vocabulary_scores_higher_than_unrelated_text():
    embedder = HashingEmbedder()
    query, related, unrelated = embedder.embed(
        [
            "database query optimization",
            "query optimization across database tables",
            "mentoring high school students",
        ]
    )

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b))

    assert cosine(query, related) > cosine(query, unrelated)


# --- generation ---


def test_extractive_generator_cannot_invent_content():
    chunks = [ScoredChunk(chunk_id=None, text="Cut 1,001 queries to 1", section="API", score=0.9)]
    output = ExtractiveGenerator().generate("backend role", chunks)

    # Every non-boilerplate token must have come from the retrieved passage.
    assert "1,001 queries to 1" in output
    assert "[1]" in output


def test_extractive_generator_says_so_when_nothing_was_retrieved():
    assert "No relevant passages" in ExtractiveGenerator().generate("anything", [])


def test_context_is_numbered_so_the_model_has_something_to_cite():
    chunks = [
        ScoredChunk(chunk_id=None, text="first", section="A", score=0.9),
        ScoredChunk(chunk_id=None, text="second", section="B", score=0.8),
    ]
    context = format_context(chunks)

    assert "[1] (A) first" in context
    assert "[2] (B) second" in context


# --- pipeline and endpoints ---


async def test_ingest_indexes_every_bullet(auth_client: AsyncClient):
    response = await auth_client.post(
        "/rag/documents", json={"document_name": "resume", "text": RESUME}
    )

    assert response.status_code == 200
    assert response.json() == {"document_name": "resume", "chunks_indexed": 4}


async def test_reingesting_the_same_document_replaces_rather_than_duplicates(
    auth_client: AsyncClient,
):
    await auth_client.post("/rag/documents", json={"document_name": "resume", "text": RESUME})
    await auth_client.post("/rag/documents", json={"document_name": "resume", "text": RESUME})

    response = await auth_client.post(
        "/rag/query", json={"job_description": "backend engineer", "top_k": 20}
    )

    # 8 would mean the first ingest's chunks are still in the index, competing
    # with the second's.
    assert len(response.json()["sources"]) == 4


async def test_query_ranks_the_relevant_passage_first(auth_client: AsyncClient):
    await auth_client.post("/rag/documents", json={"document_name": "resume", "text": RESUME})

    response = await auth_client.post(
        "/rag/query",
        json={
            "job_description": (
                "We need someone strong on database query optimization and SQL "
                "across large tables."
            ),
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert sources, "retrieval returned nothing"
    assert "1,001" in sources[0]["text"]
    # Scores must be returned best first.
    assert [s["score"] for s in sources] == sorted(
        (s["score"] for s in sources), reverse=True
    )


async def test_top_k_bounds_the_result_count(auth_client: AsyncClient):
    await auth_client.post("/rag/documents", json={"document_name": "resume", "text": RESUME})

    response = await auth_client.post(
        "/rag/query", json={"job_description": "engineer", "top_k": 2}
    )

    assert len(response.json()["sources"]) == 2


async def test_query_against_an_empty_index_returns_no_sources(auth_client: AsyncClient):
    response = await auth_client.post(
        "/rag/query", json={"job_description": "backend engineer"}
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []


# --- authorization ---


@pytest.mark.security
async def test_rag_endpoints_reject_anonymous_callers(client: AsyncClient):
    """A resume is the most personal document here. Neither route may be open."""
    ingest = await client.post("/rag/documents", json={"document_name": "r", "text": RESUME})
    query = await client.post("/rag/query", json={"job_description": "backend"})

    assert ingest.status_code == 401
    assert query.status_code == 401


@pytest.mark.security
async def test_retrieval_never_crosses_users(client: AsyncClient):
    """One user's resume must not surface in another user's retrieval."""
    await client.post(
        "/auth/register", json={"email": "owner@example.com", "password": "ownerpass123"}
    )
    owner_token = (
        await client.post(
            "/auth/login",
            data={"username": "owner@example.com", "password": "ownerpass123"},
        )
    ).json()["access_token"]

    await client.post(
        "/rag/documents",
        json={"document_name": "resume", "text": RESUME},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    await client.post(
        "/auth/register", json={"email": "other@example.com", "password": "otherpass123"}
    )
    other_token = (
        await client.post(
            "/auth/login",
            data={"username": "other@example.com", "password": "otherpass123"},
        )
    ).json()["access_token"]

    response = await client.post(
        "/rag/query",
        json={"job_description": "database query optimization"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == [], "another user's resume leaked into retrieval"


@pytest.mark.security
async def test_oversized_resume_is_rejected_before_it_is_embedded(auth_client: AsyncClient):
    """CWE-400. Chunking and embedding cost real CPU, so bound the input."""
    response = await auth_client.post(
        "/rag/documents", json={"document_name": "resume", "text": "x" * 200_001}
    )

    assert response.status_code == 422


@pytest.mark.security
async def test_top_k_is_bounded(auth_client: AsyncClient):
    """An unbounded top_k is a cheap way to make the server do expensive work."""
    response = await auth_client.post(
        "/rag/query", json={"job_description": "engineer", "top_k": 10_000}
    )

    assert response.status_code == 422
