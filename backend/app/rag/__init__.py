"""Retrieval-augmented generation over the user's own resume corpus.

Given a job description, retrieve the passages of the user's resume that are
actually relevant and generate tailoring suggestions that cite them. The
citation requirement is the point: an ungrounded LLM will happily invent
achievements, and an invented achievement on a resume is a lie the user has to
defend in an interview.

Layout:
    chunker.py     resume text -> retrievable passages
    embeddings.py  passage -> vector, with a swappable backend
    store.py       vector search, with a pgvector and a numpy backend
    generation.py  retrieved passages -> grounded suggestions
    pipeline.py    the three above, wired together
"""
