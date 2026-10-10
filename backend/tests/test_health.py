from unittest.mock import MagicMock

from app.core.redis import get_redis


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "up", "redis": "up"}


def test_health_degraded_when_redis_down(client):
    broken = MagicMock()
    broken.ping.side_effect = ConnectionError("down")
    client.app.dependency_overrides[get_redis] = lambda: broken
    body = client.get("/health").json()
    assert body["status"] == "degraded"
    assert body["redis"] == "down"
    assert body["database"] == "up"
