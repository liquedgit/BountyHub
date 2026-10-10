from app.ai import factory as keys
from app.models import Program, ReconJob
from app.models.bounty import Finding, FindingStatus, Note, Severity, Target
from app.repositories.settings import SettingsRepository

STATUSES = {s.value for s in FindingStatus}
SEVERITIES = {s.value for s in Severity}


def test_empty_database_returns_zeros_with_every_enum_key(auth_client):
    r = auth_client.get("/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["programs"] == body["targets"] == body["notes"] == 0
    assert body["findings"]["total"] == body["findings"]["open"] == 0
    assert body["findings"]["by_status"] == dict.fromkeys(STATUSES, 0)
    assert body["findings"]["by_severity"] == dict.fromkeys(SEVERITIES, 0)
    assert body["payout_cents_paid"] == 0
    assert body["scans"] == {"total": 0, "active": 0}
    assert body["ai_configured"] is False
    assert body["recent_findings"] == [] and body["recent_scans"] == []


def seed(db):
    prog = Program(name="Acme")
    db.add(prog)
    db.flush()
    db.add_all(
        [
            Target(program_id=prog.id, value="a.acme.com"),
            Note(program_id=prog.id, title="n", body="b"),
        ]
    )
    spec = [
        ("f1", FindingStatus.NEW, Severity.HIGH, None),
        ("f2", FindingStatus.TRIAGED, Severity.LOW, None),
        ("f3", FindingStatus.PAID, Severity.CRITICAL, 5000),
        ("f4", FindingStatus.PAID, Severity.HIGH, 2500),
        ("f5", FindingStatus.DUPLICATE, Severity.LOW, None),
        ("f6", FindingStatus.RESOLVED, Severity.INFO, None),
        ("f7", FindingStatus.NEW, Severity.MEDIUM, None),
    ]
    for title, st, sev, payout in spec:
        db.add(
            Finding(program_id=prog.id, title=title, status=st, severity=sev, payout_cents=payout)
        )
        db.flush()
    for st in ("queued", "running", "completed", "failed", "completed", "completed"):
        db.add(ReconJob(program_id=prog.id, targets=["a.acme.com"], status=st))
        db.flush()
    db.commit()
    return prog


def test_seeded_summary(auth_client, db_session):
    seed(db_session)
    body = auth_client.get("/dashboard/summary").json()
    assert (body["programs"], body["targets"], body["notes"]) == (1, 1, 1)
    f = body["findings"]
    assert f["total"] == 7 and f["open"] == 3
    assert f["by_status"]["new"] == 2 and f["by_status"]["paid"] == 2
    assert f["by_status"].keys() == STATUSES and f["by_severity"].keys() == SEVERITIES
    assert f["by_severity"]["high"] == 2 and f["by_severity"]["critical"] == 1
    assert body["payout_cents_paid"] == 7500
    assert body["scans"] == {"total": 6, "active": 2}
    rf = body["recent_findings"]
    assert len(rf) == 5 and [x["title"] for x in rf] == ["f7", "f6", "f5", "f4", "f3"]
    assert rf[0]["program_name"] == "Acme" and rf[0]["updated_at"]
    rs = body["recent_scans"]
    assert len(rs) == 5
    assert [x["id"] for x in rs] == sorted((x["id"] for x in rs), reverse=True)
    assert rs[0]["program_name"] == "Acme" and rs[0]["target_count"] == 1


def test_ai_configured_requires_provider_and_credential(auth_client, db_session):
    repo = SettingsRepository(db_session)
    repo.set(keys.KEY_PROVIDER, keys.PROVIDER_CLAUDE)
    assert auth_client.get("/dashboard/summary").json()["ai_configured"] is False
    repo.set(keys.KEY_CLAUDE_TOKEN, "secret")
    assert auth_client.get("/dashboard/summary").json()["ai_configured"] is True
