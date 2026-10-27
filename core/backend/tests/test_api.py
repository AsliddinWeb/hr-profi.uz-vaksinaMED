from fastapi.testclient import TestClient

from app import __version__
from app.main import create_app


def test_liveness_and_meta_defaults():
    with TestClient(create_app()) as client:
        assert client.get("/api/health").json() == {"status": "ok"}

        meta = client.get("/api/v1/meta").json()
        assert meta["version"] == __version__
        assert meta["extension"] is False
        assert "attendance" in meta["modules"]
        assert meta["brand"]["name"] == "HR-Profi"
