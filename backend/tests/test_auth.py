import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "new@example.com", "password": "securepass"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    await client.post("/auth/register", json={"email": "dup@example.com", "password": "pass"})
    resp = await client.post("/auth/register", json={"email": "dup@example.com", "password": "pass"})
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={"email": "login@example.com", "password": "mypass"})
    resp = await client.post("/auth/login", data={"username": "login@example.com", "password": "mypass"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={"email": "wrong@example.com", "password": "correct"})
    resp = await client.post("/auth/login", data={"username": "wrong@example.com", "password": "incorrect"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/auth/login", data={"username": "nobody@example.com", "password": "pass"})
    assert resp.status_code == 401
