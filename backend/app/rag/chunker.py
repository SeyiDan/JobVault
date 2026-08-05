"""Split a resume into retrievable passages.

A resume is not prose, so fixed-width character chunking is the wrong tool: it
cuts bullets in half and strands a metric from the achievement it belongs to.
Resumes are already structured as headings and bullets, so the chunker follows
that structure instead.

Two rules do most of the work:

1. One bullet is one chunk. A bullet is the unit a recruiter reads and the unit
   the user would reuse on a tailored resume, so it is the unit worth retrieving.
2. Every chunk carries its section heading. "Reduced 1,001 queries to 1" is
   ambiguous on its own; "Enterprise e-Commerce API / Reduced 1,001 queries to 1"
   is not, and the heading text meaningfully improves the embedding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A markdown heading, or a bare line in Title Case that looks like a section
# label (resumes exported to text often lose their "#" markers).
_HEADING = re.compile(r"^\s*(#{1,6})\s+(.*\S)\s*$")
_BULLET = re.compile(r"^\s*[-*•]\s+(.*\S)\s*$")

# Bullets shorter than this are almost always fragments left by a bad PDF text
# extraction ("Python", "2023"), not achievements. Retrieving them adds noise.
MIN_CHUNK_CHARS = 25

# Long paragraphs get split on sentence boundaries so a single wall of text does
# not dominate every retrieval simply by containing every keyword.
MAX_CHUNK_CHARS = 600


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage plus where it came from."""

    text: str
    section: str
    ordinal: int

    @property
    def embedding_text(self) -> str:
        """What actually gets embedded: the passage prefixed by its section."""
        return f"{self.section}: {self.text}" if self.section else self.text


def _split_long(text: str) -> list[str]:
    """Break an over-long passage on sentence boundaries, never mid-word."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        # +1 for the space that will rejoin them.
        if current and len(current) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)

    # A single sentence longer than the cap still has to go somewhere. Emitting
    # it whole beats truncating a bullet and losing its metric.
    return parts or [text]


def chunk_resume(text: str) -> list[Chunk]:
    """Split resume text into passages, each tagged with its section heading."""
    chunks: list[Chunk] = []
    section = ""
    # Lines buffered for the current passage, and whether that passage started
    # with a bullet marker. Bullets wrap onto continuation lines constantly, both
    # in hand-written markdown and in text extracted from a PDF, so a plain
    # non-bullet line directly under an open bullet belongs to that bullet. Left
    # unhandled, "cutting 1,001 queries down to 1." becomes its own chunk,
    # stranded from the achievement it is the payoff of.
    buffer: list[str] = []
    in_bullet = False

    def flush() -> None:
        """Emit whatever is buffered as one passage."""
        nonlocal buffer, in_bullet
        joined = " ".join(buffer).strip()
        buffer = []
        in_bullet = False
        if len(joined) < MIN_CHUNK_CHARS:
            return
        for part in _split_long(joined):
            chunks.append(Chunk(text=part, section=section, ordinal=len(chunks)))

    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            flush()
            section = heading.group(2)
            continue

        bullet = _BULLET.match(line)
        if bullet:
            # A new bullet always ends the previous passage.
            flush()
            buffer = [bullet.group(1).strip()]
            in_bullet = True
            continue

        if not line.strip():
            flush()
            continue

        # A continuation of the open bullet, or ordinary prose.
        buffer.append(line.strip())

    flush()
    return chunks
