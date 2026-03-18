import csv
import io
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Job, User
from app.schemas import JobCreate, JobResponse, JobUpdate

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    status: str | None = Query(None),
    tag: str | None = Query(None),
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).where(Job.user_id == user.id)

    if status:
        query = query.where(Job.status == status)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.notes.ilike(pattern),
            )
        )

    query = query.order_by(Job.date_saved.desc())
    result = await db.execute(query)
    jobs = result.scalars().all()

    if tag:
        jobs = [j for j in jobs if tag in (j.tags or [])]

    return jobs


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    payload: JobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.url:
        result = await db.execute(
            select(Job).where(Job.user_id == user.id, Job.url == payload.url)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Job with this URL already exists")

    now = datetime.now(timezone.utc)
    timeline = payload.timeline or [{"date": now.isoformat(), "event": "Job saved", "type": "manual"}]

    job = Job(
        user_id=user.id,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        salary=payload.salary,
        url=payload.url,
        description=payload.description[:3000] if payload.description else "",
        status=payload.status,
        notes=payload.notes,
        tags=payload.tags,
        reminder_date=payload.reminder_date,
        apply_url=payload.apply_url,
        timeline=timeline,
        date_saved=now,
        last_updated=now,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == _uuid.UUID(job_id), Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    payload: JobUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == _uuid.UUID(job_id), Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    update_data = payload.model_dump(exclude_unset=True)

    now = datetime.now(timezone.utc).isoformat()
    old_status = job.status
    for field, value in update_data.items():
        setattr(job, field, value)

    timeline = list(job.timeline or [])
    if "status" in update_data and update_data["status"] != old_status:
        timeline.append({
            "date": now,
            "event": f"Status changed from {old_status} to {update_data['status']}",
            "type": "manual",
        })
    else:
        timeline.append({"date": now, "event": "Job edited", "type": "manual"})
    job.timeline = timeline

    job.last_updated = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == _uuid.UUID(job_id), Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()


@router.get("/export/csv")
async def export_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.user_id == user.id).order_by(Job.date_saved.desc())
    )
    jobs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Company", "Location", "Salary", "Status", "Tags", "URL", "Notes", "Date Saved", "Last Updated"])
    for j in jobs:
        writer.writerow([
            j.title, j.company, j.location, j.salary, j.status,
            "; ".join(j.tags or []), j.url, j.notes,
            j.date_saved.isoformat() if j.date_saved else "",
            j.last_updated.isoformat() if j.last_updated else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=jobvault-export.csv"},
    )


@router.post("/import", response_model=list[JobResponse])
async def import_jobs(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    text = content.decode("utf-8")
    now = datetime.now(timezone.utc)

    existing_result = await db.execute(select(Job.url).where(Job.user_id == user.id))
    existing_urls = {row[0] for row in existing_result.all() if row[0]}

    imported = []

    if file.filename.endswith(".json"):
        import json
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("jobs", [])
    else:
        reader = csv.DictReader(io.StringIO(text))
        items = list(reader)

    for item in items:
        url = item.get("url") or item.get("URL") or ""
        if url and url in existing_urls:
            continue

        job = Job(
            user_id=user.id,
            title=item.get("title") or item.get("Title") or "",
            company=item.get("company") or item.get("Company") or "",
            location=item.get("location") or item.get("Location") or "",
            salary=item.get("salary") or item.get("Salary") or "",
            url=url,
            description=item.get("description") or "",
            status=item.get("status") or item.get("Status") or "Saved",
            notes=item.get("notes") or item.get("Notes") or "",
            tags=item.get("tags") if isinstance(item.get("tags"), list)
                else [t.strip() for t in (item.get("Tags") or "").split(";") if t.strip()],
            timeline=[{"date": now.isoformat(), "event": "Imported", "type": "manual"}],
            date_saved=now,
            last_updated=now,
        )
        db.add(job)
        imported.append(job)
        if url:
            existing_urls.add(url)

    await db.commit()
    for job in imported:
        await db.refresh(job)
    return imported
