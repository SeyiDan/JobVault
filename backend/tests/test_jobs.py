import pytest
from httpx import AsyncClient


SAMPLE_JOB = {
    "title": "Software Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "salary": "$120k - $150k",
    "url": "https://example.com/job/123",
    "description": "Build cool stuff",
    "status": "Saved",
    "notes": "Great opportunity",
    "tags": ["Remote", "Python"],
}


@pytest.mark.asyncio
async def test_create_job(auth_client: AsyncClient):
    resp = await auth_client.post("/jobs", json=SAMPLE_JOB)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Software Engineer"
    assert data["company"] == "Acme Corp"
    assert data["tags"] == ["Remote", "Python"]
    assert "id" in data


@pytest.mark.asyncio
async def test_create_duplicate_url(auth_client: AsyncClient):
    await auth_client.post("/jobs", json=SAMPLE_JOB)
    resp = await auth_client.post("/jobs", json=SAMPLE_JOB)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_jobs(auth_client: AsyncClient):
    await auth_client.post("/jobs", json=SAMPLE_JOB)
    await auth_client.post("/jobs", json={**SAMPLE_JOB, "url": "https://example.com/job/456", "title": "Backend Dev"})

    resp = await auth_client.get("/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_jobs_filter_status(auth_client: AsyncClient):
    await auth_client.post("/jobs", json=SAMPLE_JOB)
    await auth_client.post("/jobs", json={**SAMPLE_JOB, "url": "https://example.com/456", "status": "Applied"})

    resp = await auth_client.get("/jobs", params={"status": "Applied"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "Applied"


@pytest.mark.asyncio
async def test_list_jobs_search(auth_client: AsyncClient):
    await auth_client.post("/jobs", json=SAMPLE_JOB)
    await auth_client.post("/jobs", json={**SAMPLE_JOB, "url": "https://other.com/1", "company": "BigTech"})

    resp = await auth_client.get("/jobs", params={"search": "BigTech"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_job(auth_client: AsyncClient):
    create_resp = await auth_client.post("/jobs", json=SAMPLE_JOB)
    job_id = create_resp.json()["id"]

    resp = await auth_client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Software Engineer"


@pytest.mark.asyncio
async def test_get_job_not_found(auth_client: AsyncClient):
    resp = await auth_client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_job(auth_client: AsyncClient):
    create_resp = await auth_client.post("/jobs", json=SAMPLE_JOB)
    job_id = create_resp.json()["id"]

    resp = await auth_client.put(f"/jobs/{job_id}", json={"status": "Applied", "notes": "Applied today"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "Applied"
    assert data["notes"] == "Applied today"

    timeline_events = [e["event"] for e in data["timeline"]]
    assert any("Status changed" in e for e in timeline_events)


@pytest.mark.asyncio
async def test_delete_job(auth_client: AsyncClient):
    create_resp = await auth_client.post("/jobs", json=SAMPLE_JOB)
    job_id = create_resp.json()["id"]

    resp = await auth_client.delete(f"/jobs/{job_id}")
    assert resp.status_code == 204

    resp = await auth_client.get(f"/jobs/{job_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_csv(auth_client: AsyncClient):
    await auth_client.post("/jobs", json=SAMPLE_JOB)
    resp = await auth_client.get("/jobs/export/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Software Engineer" in resp.text


@pytest.mark.asyncio
async def test_unauthenticated_access(client: AsyncClient):
    resp = await client.get("/jobs")
    assert resp.status_code == 401
