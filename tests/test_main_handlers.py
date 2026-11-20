import pytest
from fastapi.responses import HTMLResponse

from app.main import health, serve_frontend


@pytest.mark.asyncio
async def test_health_handler_returns_ok_status():
    response = await health()

    assert response == {"status": "ok", "version": "1.0.0"}


@pytest.mark.asyncio
async def test_serve_frontend_returns_html_response():
    response = await serve_frontend()

    assert isinstance(response, HTMLResponse)
    assert "<!DOCTYPE html>" in response.body.decode("utf-8")
