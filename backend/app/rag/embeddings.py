"""Text to vector, with a swappable backend.

Two backends, chosen explicitly by the EMBEDDING_BACKEND environment variable:

`sentence-transformers`
    The real one. Runs `all-MiniLM-L6-v2` locally, so there is no API key, no
    per-query cost and no text leaving the machine. It pulls in torch, which is
    hundreds of megabytes, so it lives in `requirements-rag.txt` rather than
    `requirements.txt`. The API image and the CI test job stay small; anyone
    running the real pipeline or the eval installs the extra.

`hashing`
    A deterministic, dependency-free hashed bag-of-words embedding used by the
    tests. It is a genuinely worse retriever, which is the point: the test suite
    should assert the plumbing works without downloading a model, and the eval
    harness measures quality separately with the real backend.

The backend is never selected implicitly. Falling back to `hashing` because
torch failed to import would silently change what "relevant" means and make an
eval number meaningless, so a missing dependency raises instead.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from functools import lru_cache
from typing import Protocol

# all-MiniLM-L6-v2 emits 384 dimensions. The hashing backend matches it so both
# backends write into the same column and one can be swapped for the other
# without a schema change.
EMBEDDING_DIM = 384

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    """Anything that can turn text into a fixed-length unit vector."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vector: list[float]) -> list[float]:
    """Scale to unit length so a dot product is a cosine similarity."""
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0:
        return vector
    return [component / norm for component in vector]


class HashingEmbedder:
    """Deterministic hashed bag-of-words. No model download, no network.

    Each token is hashed to a dimension and accumulated, then the vector is
    normalized. Two texts sharing vocabulary land near each other, which is
    enough to prove retrieval and ranking work. It has no notion of synonyms,
    so it will not tell you whether the pipeline is any *good*.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * EMBEDDING_DIM
            for token in _TOKEN.findall(text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
                # The last bit picks a sign, so unrelated tokens colliding on a
                # dimension are as likely to cancel as to reinforce.
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[index] += sign
            vectors.append(_normalize(vector))
        return vectors


class SentenceTransformerEmbedder:
    """Local `all-MiniLM-L6-v2`. Requires `requirements-rag.txt`."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on the extra
            raise RuntimeError(
                "EMBEDDING_BACKEND=sentence-transformers needs the optional ML "
                "dependencies. Install them with:\n"
                "    pip install -r requirements-rag.txt\n"
                "Or set EMBEDDING_BACKEND=hashing for a dependency-free "
                "backend (much weaker retrieval; do not use it for the eval)."
            ) from exc

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            # Normalizing here means the store can use a plain dot product and
            # the two backends stay interchangeable.
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(component) for component in vector] for vector in vectors]


@lru_cache(maxsize=None)
def get_embedder(backend: str | None = None) -> Embedder:
    """Return the configured embedder. Cached: loading the model is slow."""
    backend = backend or os.getenv("EMBEDDING_BACKEND", "sentence-transformers")
    if backend == "hashing":
        return HashingEmbedder()
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder()
    raise ValueError(
        f"Unknown EMBEDDING_BACKEND {backend!r}. "
        "Expected 'sentence-transformers' or 'hashing'."
    )
