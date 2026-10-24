"""Integration tests for Authentication API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db.session import init_db


@pytest.mark.asyncio
async def test_auth_flow_register_login_me():
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register new organization user
        unique_email = "test.lead@enterprise.ai"
        reg_payload = {
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Test Lead",
            "organization_name": "Test Engineering Corp"
        }
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code in [201, 400]

        # 2. Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": "SecurePassword123!"
        })
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # 3. Get /me
        me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == unique_email
        assert len(me_data["organizations"]) > 0
