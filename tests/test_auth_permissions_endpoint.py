from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.auth import router as auth_router


def test_permissions_endpoint_returns_role_matrix():
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)

    response = client.get("/api/auth/permissions")
    assert response.status_code == 200

    data = response.json()
    assert "admin" in data
    assert "equipment" in data["admin"]
    assert "read" in data["admin"]["equipment"]
