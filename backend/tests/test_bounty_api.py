def mk_program(client, **kw):
    r = client.post("/programs", json={"name": "Acme", "platform": "hackerone", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_program_crud(client):
    p = mk_program(client, reward_info="$100-$5000")
    pid = p["id"]
    assert p["platform"] == "hackerone"
    assert client.get(f"/programs/{pid}").json()["name"] == "Acme"
    assert len(client.get("/programs").json()) == 1
    r = client.patch(f"/programs/{pid}", json={"name": "Acme 2"})
    assert r.json()["name"] == "Acme 2" and r.json()["platform"] == "hackerone"
    assert client.delete(f"/programs/{pid}").status_code == 204
    assert client.get(f"/programs/{pid}").status_code == 404


def test_program_validation(client):
    assert client.post("/programs", json={"name": ""}).status_code == 422
    assert client.get("/programs/999").status_code == 404


def test_scope_rules_crud_and_validation(client):
    pid = mk_program(client)["id"]
    r = client.post(f"/programs/{pid}/scope-rules", json={"action": "in", "type": "wildcard", "value": "*.acme.com"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client.post(f"/programs/{pid}/scope-rules", json={"action": "maybe", "type": "domain", "value": "x"}).status_code == 422
    assert client.post(f"/programs/{pid}/scope-rules", json={"action": "in", "type": "cidr", "value": "x"}).status_code == 422
    assert client.patch(f"/programs/{pid}/scope-rules/{rid}", json={"value": "*.acme.io"}).json()["value"] == "*.acme.io"
    assert len(client.get(f"/programs/{pid}/scope-rules").json()) == 1
    assert client.delete(f"/programs/{pid}/scope-rules/{rid}").status_code == 204
    assert client.get(f"/programs/{pid}/scope-rules/{rid}").status_code == 404


def test_scope_check_endpoint(client):
    pid = mk_program(client)["id"]
    for rule in [
        {"action": "in", "type": "wildcard", "value": "*.acme.com"},
        {"action": "out", "type": "domain", "value": "admin.acme.com"},
    ]:
        client.post(f"/programs/{pid}/scope-rules", json=rule)
    chk = lambda h: client.post(f"/programs/{pid}/scope-check", json={"host": h}).json()  # noqa: E731
    assert chk("www.acme.com")["in_scope"] is True
    assert chk("admin.acme.com")["in_scope"] is False
    assert chk("evil.com")["in_scope"] is False
    assert client.post("/programs/999/scope-check", json={"host": "a.com"}).status_code == 404


def test_targets_crud(client):
    pid = mk_program(client)["id"]
    r = client.post(f"/programs/{pid}/targets", json={"value": "www.acme.com", "description": "main"})
    assert r.status_code == 201
    tid = r.json()["id"]
    assert client.patch(f"/programs/{pid}/targets/{tid}", json={"description": "x"}).json()["description"] == "x"
    assert client.get(f"/programs/{pid}/targets").json()[0]["value"] == "www.acme.com"
    assert client.delete(f"/programs/{pid}/targets/{tid}").status_code == 204


def test_findings_crud_status_severity_payout(client):
    pid = mk_program(client)["id"]
    tid = client.post(f"/programs/{pid}/targets", json={"value": "a.acme.com"}).json()["id"]
    r = client.post(
        f"/programs/{pid}/findings",
        json={"title": "XSS", "severity": "high", "target_id": tid, "description": "# md"},
    )
    assert r.status_code == 201
    f = r.json()
    assert f["status"] == "new" and f["severity"] == "high"
    r = client.patch(f"/programs/{pid}/findings/{f['id']}", json={"status": "paid", "payout_cents": 150000})
    assert r.json()["status"] == "paid" and r.json()["payout_cents"] == 150000
    assert client.post(f"/programs/{pid}/findings", json={"title": "x", "severity": "huge"}).status_code == 422
    assert client.post(f"/programs/{pid}/findings", json={"title": "x", "payout_cents": -1}).status_code == 422
    assert client.delete(f"/programs/{pid}/findings/{f['id']}").status_code == 204


def test_cross_program_isolation(client):
    p1, p2 = mk_program(client)["id"], mk_program(client, name="Other")["id"]
    t1 = client.post(f"/programs/{p1}/targets", json={"value": "a.com"}).json()["id"]
    assert client.get(f"/programs/{p2}/targets/{t1}").status_code == 404
    r = client.post(f"/programs/{p2}/findings", json={"title": "x", "target_id": t1})
    assert r.status_code == 422


def test_notes_crud_attached_to_finding(client):
    pid = mk_program(client)["id"]
    fid = client.post(f"/programs/{pid}/findings", json={"title": "SQLi"}).json()["id"]
    r = client.post(f"/programs/{pid}/notes", json={"title": "Recon", "body_md": "## hi\n- a"})
    assert r.status_code == 201 and r.json()["finding_id"] is None
    r = client.post(f"/programs/{pid}/notes", json={"title": "PoC", "body_md": "`curl`", "finding_id": fid})
    assert r.json()["finding_id"] == fid
    nid = r.json()["id"]
    assert client.patch(f"/programs/{pid}/notes/{nid}", json={"body_md": "new"}).json()["body_md"] == "new"
    assert len(client.get(f"/programs/{pid}/notes").json()) == 2
    assert client.post(f"/programs/{pid}/notes", json={"title": "x", "finding_id": 999}).status_code == 422
    assert client.delete(f"/programs/{pid}/notes/{nid}").status_code == 204


def test_delete_program_cascades(client):
    pid = mk_program(client)["id"]
    client.post(f"/programs/{pid}/targets", json={"value": "a.com"})
    client.post(f"/programs/{pid}/scope-rules", json={"action": "in", "type": "domain", "value": "a.com"})
    client.post(f"/programs/{pid}/findings", json={"title": "x"})
    assert client.delete(f"/programs/{pid}").status_code == 204
    assert client.get(f"/programs/{pid}/targets").status_code == 404
