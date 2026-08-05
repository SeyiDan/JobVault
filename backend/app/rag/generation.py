"""Turn retrieved passages into grounded tailoring suggestions.

The prompt is deliberately restrictive. An LLM asked to "improve this resume"
will invent plausible achievements, and a plausible invented achievement is the
worst possible output here: it survives review, reaches a real application, and
becomes something the user has to defend in an interview. So the model is given
retrieved passages, told it may only rephrase and re-emphasise what is in them,
and required to cite the passage each suggestion came from.

Two backends, chosen by GENERATION_BACKEND:

`groq`
    Calls the Groq API, which has a free tier and is already used elsewhere in
    the user's projects. Needs GROQ_API_KEY.

`extractive`
    No LLM at all. Returns the retrieved passages ranked, with no generated
    prose. Used by the tests so the suite needs no API key and no network, and
    it is a reasonable degraded mode when no key is configured.
"""

from __future__ import annotations

import os
from typing import Protocol

import httpx

from app.rag.store import ScoredChunk

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
REQUEST_TIMEOUT_SECONDS = 30

SYSTEM_PROMPT = """\
You help a candidate tailor an existing resume to a specific job description.

You will be given numbered passages from the candidate's real resume, and a job
description. Your rules, in order of importance:

1. Never state an achievement, technology, metric or responsibility that does
   not appear in the passages. If the job asks for something the candidate does
   not have, say so plainly as a gap. Do not fill it.
2. Never invent or adjust a number. Numbers may only be copied exactly.
3. Every suggestion must cite the passage it came from as [1], [2] and so on.
4. Prefer re-emphasis and rephrasing over new content.
5. Do not use em dashes.

Return at most five suggestions, each one or two sentences, then a short "Gaps"
list naming what the job asks for that the passages do not support.
"""


class Generator(Protocol):
    """Anything that turns a query plus passages into an answer."""

    def generate(self, query: str, chunks: list[ScoredChunk]) -> str: ...


def format_context(chunks: list[ScoredChunk]) -> str:
    """Number the passages so the model has something concrete to cite."""
    return "\n".join(
        f"[{index}] ({chunk.section}) {chunk.text}"
        for index, chunk in enumerate(chunks, start=1)
    )


class ExtractiveGenerator:
    """No LLM. Returns the retrieved passages, best first.

    Cannot hallucinate, because it never generates a token. That makes it the
    honest default when no API key is configured, and it keeps the test suite
    free of network calls.
    """

    def generate(self, query: str, chunks: list[ScoredChunk]) -> str:
        if not chunks:
            return "No relevant passages found in the indexed resume."
        lines = ["Most relevant passages from your resume, best match first:", ""]
        lines += [
            f"[{index}] ({chunk.section}) {chunk.text}"
            for index, chunk in enumerate(chunks, start=1)
        ]
        return "\n".join(lines)


class GroqGenerator:
    """Groq chat completions. Free tier, no new spend."""

    def __init__(self, api_key: str, model: str = DEFAULT_GROQ_MODEL) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, query: str, chunks: list[ScoredChunk]) -> str:
        if not chunks:
            return "No relevant passages found in the indexed resume."

        response = httpx.post(
            GROQ_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                # Low but not zero: the task is constrained rephrasing, and
                # sampling variety buys nothing while raising drift risk.
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Job description:\n{query}\n\n"
                            f"Passages from the candidate's resume:\n"
                            f"{format_context(chunks)}"
                        ),
                    },
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def get_generator() -> Generator:
    """Return the configured generator.

    Unlike the embedder, falling back here is safe: dropping to extractive mode
    yields less useful output but cannot produce a wrong claim, and it is better
    than a 500 when a key is simply absent.
    """
    backend = os.getenv("GENERATION_BACKEND", "groq")
    if backend == "extractive":
        return ExtractiveGenerator()
    if backend == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return ExtractiveGenerator()
        return GroqGenerator(api_key)
    raise ValueError(
        f"Unknown GENERATION_BACKEND {backend!r}. Expected 'groq' or 'extractive'."
    )
