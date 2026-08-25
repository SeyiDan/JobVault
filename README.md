# JobVault

A job-application tracker with a **retrieval-augmented generation pipeline** that reads a job
description and tells you which parts of your resume to lead with. FastAPI and PostgreSQL
backend, Chrome extension front end.

**The retrieval is measured, not asserted.** Against a labeled set of 15 job-description queries
over 20 resume passages, it surfaces **81.1% of the relevant passages in the top 5**, against
23.3% for a random baseline, at an MRR of 0.880 versus 0.207.
[How it works](#resume-retrieval) · [full results](./eval/results.md)

Generation is constrained to cite the passage every suggestion came from, and may not invent an
achievement or change a number. An invented achievement is one you have to defend in an interview.

The extension side extracts job details from LinkedIn, Indeed, Greenhouse, Lever, Workday,
Glassdoor and Wellfound with one click, tracks application status, sets reminders, and syncs
across devices through the backend API.

## Tech Stack

**Backend:** Python, FastAPI, SQLAlchemy (async), asyncpg, PostgreSQL, JWT (python-jose), bcrypt

**Extension:** JavaScript, Chrome Extensions Manifest V3, HTML, CSS

**Infrastructure:** Docker, Docker Compose, pytest

## Project Structure

```
JobVault/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI application entry point
│   │   ├── config.py          # Environment-based settings
│   │   ├── database.py        # Async SQLAlchemy engine and session
│   │   ├── models.py          # User and Job ORM models
│   │   ├── schemas.py         # Pydantic request/response schemas
│   │   ├── auth.py            # JWT creation, verification, password hashing
│   │   └── routers/
│   │       ├── auth.py        # POST /auth/register, POST /auth/login
│   │       └── jobs.py        # Full CRUD, CSV export, file import
│   ├── tests/
│   │   ├── conftest.py        # Test fixtures (async client, auth helper)
│   │   ├── test_auth.py       # Auth endpoint tests
│   │   ├── test_jobs.py       # Job CRUD endpoint tests
│   │   ├── test_rag.py        # Retrieval pipeline, incl. 4 security-marked tests
│   │   └── test_security.py   # Security regressions (module-level marker)
│   ├── Dockerfile
│   └── requirements.txt
├── manifest.json               # Chrome extension manifest (MV3)
├── popup.html / popup.js       # Extension popup UI
├── jobs.html / jobs.js         # Saved jobs dashboard
├── content.js                  # Job data extraction (per-site selectors)
├── background.js               # Service worker (alarms, auto-check, sync)
├── fab.js                      # Floating quick-save button on job pages
├── api.js                      # API client for extension-to-backend sync
├── docker-compose.yml          # FastAPI + PostgreSQL
└── .gitignore
```

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Google Chrome (for the extension)

### Run the Backend

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker compose up --build
```

`docker-compose.yml` declares `SECRET_KEY` as required, so compose aborts before starting
anything if it is unset. It reads the **invoking shell** or a `.env` at the repository root;
`backend/.env` is for running the API directly and compose never looks at it.

This starts:
- **API** at `http://localhost:8000`
- **PostgreSQL** at `localhost:5432`
- **Swagger docs** at `http://localhost:8000/docs`

Tables are created automatically on first startup.

### Load the Extension

1. Open `chrome://extensions/` in Chrome
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** and select the `JobVault/` project root
4. Navigate to any job posting and click the extension icon

### Connect Extension to Backend

1. Click **Sync** in the extension popup
2. Register with an email and password
3. Jobs will now save to both local storage and the API

## API Endpoints

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create a new account |
| POST | `/auth/login` | Get a JWT access token |

### Jobs (requires authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List all jobs (supports `?status=`, `?tag=`, `?search=` filters) |
| POST | `/jobs` | Create a job |
| GET | `/jobs/{id}` | Get a single job |
| PUT | `/jobs/{id}` | Update a job |
| DELETE | `/jobs/{id}` | Delete a job |
| GET | `/jobs/export/csv` | Download all jobs as CSV |
| POST | `/jobs/import` | Import jobs from CSV or JSON file |

### Resume retrieval (requires authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rag/documents` | Index a resume. Chunks it by bullet, embeds each passage, stores the vectors. Re-posting the same `document_name` replaces that document's chunks |
| POST | `/rag/query` | Retrieve the resume passages most relevant to a job description and generate tailoring suggestions that cite them |

See [Resume retrieval](#resume-retrieval) below for how it works.

## Supported Job Sites

| Site | Extraction |
|------|-----------|
| LinkedIn | Targeted selectors for title, company, location, salary, description |
| Indeed | Targeted selectors |
| Greenhouse | Targeted selectors |
| Lever | Targeted selectors |
| Workday | Targeted selectors |
| Glassdoor | Targeted selectors |
| Wellfound | Targeted selectors |
| Any other site | Generic fallback using meta tags and common class patterns |

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

The suite (41 backend tests: 16 functional (5 auth, 11 jobs), 17 for the retrieval
pipeline, and 8 in the security file; the `security` marker spans 12 of them, since 4 more live
in the retrieval tests) covers:
- User registration and login
- Duplicate email rejection
- Wrong password handling
- Job CRUD operations
- Status filtering and search
- CSV export
- Timeline tracking on status changes
- Unauthenticated access rejection
- Security regressions (see below)
- Resume chunking, embedding, ranking and per-user retrieval isolation

Retrieval tests run with `EMBEDDING_BACKEND=hashing`, a deterministic
dependency-free embedder, so the suite needs no model download and makes no
network call. Retrieval *quality* is measured separately by the eval harness.

Extension helpers are unit-tested with `node --test test/escape.test.js`.

## Security

Self-audited for security. See [**SECURITY-AUDIT.md**](./SECURITY-AUDIT.md) for the
six findings (a stored XSS, a hardcoded signing key, and more). Four carry a
proof-of-concept or a regression test; the remaining two are a dependency pin and a shortened
token lifetime, neither of which has a test asserting it, and
[**.github/workflows/security.yml**](./.github/workflows/security.yml) for the CI
gate (Semgrep, Trivy, gitleaks, pip-audit, ESLint no-unsanitized).

## Resume retrieval

Given a job description, find the passages of your resume that are actually
relevant and suggest how to lead with them.

```
resume text -> chunk by bullet -> embed -> pgvector
job description -> embed -> nearest passages -> LLM -> cited suggestions
```

The generation prompt is deliberately restrictive: the model may only rephrase
and re-emphasise the retrieved passages, may not invent an achievement or adjust
a number, and must cite the passage each suggestion came from. An invented
achievement on a resume is something you have to defend in an interview.

**Vector storage.** `document_chunks.embedding` is a real pgvector `vector(384)`
column on Postgres, so nearest-neighbour search happens in the database. On
SQLite it degrades to a JSON array and ranks in process, which is what keeps the
test suite fast and containerless. Both paths rank by cosine similarity over
unit vectors, so their orderings agree.

**Embeddings run locally** via `all-MiniLM-L6-v2`. No API key, no per-query cost, and no resume
text leaves the machine. It pulls in torch, so it lives in `backend/requirements-rag.txt` rather
than the base requirements, which keeps the CI job small.

**The Docker image does not include it.** `backend/Dockerfile` installs only `requirements.txt`,
while compose defaults `EMBEDDING_BACKEND=sentence-transformers`, and `embeddings.py` raises
`RuntimeError` when the extra is missing rather than falling back. So retrieval in the container
needs either `EMBEDDING_BACKEND=hashing` or a Dockerfile that installs the extra.

```bash
pip install -r backend/requirements-rag.txt   # optional, for real embeddings
python eval/run_eval.py --write               # score retrieval quality
```

**Measured quality.** `eval/` holds a labeled set of 20 resume passages and 15
job-description queries and reports recall@k and MRR against a fixed random
baseline, run against the production `sentence-transformers` backend:

| Metric | Retriever | Random baseline |
|---|---|---|
| recall@1 | 0.428 | 0.033 |
| recall@3 | 0.661 | 0.056 |
| **recall@5** | **0.811** | 0.233 |
| **MRR** | **0.880** | 0.207 |

The baseline ranks the same corpus in a fixed shuffled order. It is there so the
retriever's numbers mean something: a recall figure with nothing to compare
against is not evidence. Twenty passages and fifteen queries is a small set and I
labeled it myself, so read these as directional rather than as a benchmark.

Per-query results are in [`eval/results.md`](./eval/results.md). Regenerate and
commit the diff after any change to the chunker, the embedder or the ranking.

Generation uses Groq when `GROQ_API_KEY` is set. Without a key it returns the
retrieved passages verbatim, which cannot hallucinate.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://jobvault:jobvault@db:5432/jobvault` | PostgreSQL connection string |
| `SECRET_KEY` | none, required | JWT signing key. The app refuses to start without one, or with a known placeholder, or shorter than 32 characters |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token expiry. There is no refresh or revocation, so a leaked token is valid until it expires |
| `EMBEDDING_BACKEND` | `sentence-transformers` | `sentence-transformers` or `hashing`. Never falls back implicitly |
| `GENERATION_BACKEND` | `groq` | `groq` or `extractive` |
| `GROQ_API_KEY` | none | Optional. Without it, generation degrades to returning retrieved passages |

Copy `backend/.env.example` to `backend/.env` and update values for production.
