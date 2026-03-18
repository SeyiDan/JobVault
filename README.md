# JobVault

A Chrome extension for saving and tracking job applications, backed by a FastAPI REST API with PostgreSQL.

Extract job details from LinkedIn, Indeed, Greenhouse, Lever, Workday, Glassdoor, and Wellfound with one click. Track application status, set reminders, and sync data across devices through the backend API.

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
│   │   └── test_jobs.py       # Job CRUD endpoint tests
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
docker compose up --build
```

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

All 16 tests cover:
- User registration and login
- Duplicate email rejection
- Wrong password handling
- Job CRUD operations
- Status filtering and search
- CSV export
- Timeline tracking on status changes
- Unauthenticated access rejection

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://jobvault:jobvault@db:5432/jobvault` | PostgreSQL connection string |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiry (24 hours) |

Copy `backend/.env.example` to `backend/.env` and update values for production.
