from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine, Base
from app.routers import auth, jobs, rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # document_chunks.embedding is a pgvector column on Postgres, and the
        # type does not exist until the extension is created. This has to run
        # before create_all or the table build fails. Skipped on SQLite, where
        # the column degrades to JSON and no extension is involved.
        if conn.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="JobVault API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(rag.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
