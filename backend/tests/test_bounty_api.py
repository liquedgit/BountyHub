def mk_program(auth_client, **kw):
    r = auth_client.post("/programs", json={"name": "Acme", "platform": "hackerone", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_program_crud(auth_client):
    p = mk_program(auth_client, reward_info="$100-$5000")
    pid = p["id"]
    assert p["platform"] == "hackerone"
    assert auth_client.get(f"/programs/{pid}").json()["name"] == "Acme"
    assert len(auth_client.get("/programs").json()) == 1
    r = auth_client.patch(f"/programs/{pid}", json={"name": "Acme 2"})
    assert r.json()["name"] == "Acme 2" and r.json()["platform"] == "hackerone"
    assert auth_client.delete(f"/programs/{pid}").status_code == 204
    assert auth_client.get(f"/programs/{pid}").status_code == 404


def test_program_validation(auth_client):
    assert auth_client.post("/programs", json={"name": ""}).status_code == 422
    assert auth_client.get("/programs/999").status_code == 404


def test_scope_rules_crud_and_validation(auth_client):
    pid = mk_program(auth_client)["id"]
    r = auth_client.post(
        f"/programs/{pid}/scope-rules",
        json={"action": "in", "type": "wildcard", "value": "*.acme.com"},
    )
    assert r.status_code == 201
    rid = r.json()["id"]
    assert (
        auth_client.post(
            f"/programs/{pid}/scope-rules", json={"action": "maybe", "type": "domain", "value": "x"}
        ).status_code
        == 422
    )
    assert (
        auth_client.post(
            f"/programs/{pid}/scope-rules", json={"action": "in", "type": "cidr", "value": "x"}
        ).status_code
        == 422
    )
    assert (
        auth_client.patch(f"/programs/{pid}/scope-rules/{rid}", json={"value": "*.acme.io"}).json()[
            "value"
        ]
        == "*.acme.io"
    )
    assert len(auth_client.get(f"/programs/{pid}/scope-rules").json()) == 1
    assert auth_client.delete(f"/programs/{pid}/scope-rules/{rid}").status_code == 204
    assert auth_client.get(f"/programs/{pid}/scope-rules/{rid}").status_code == 404


def test_scope_check_endpoint(auth_client):
    pid = mk_program(auth_client)["id"]
    for rule in [
        {"action": "in", "type": "wildcard", "value": "*.acme.com"},
        {"action": "out", "type": "domain", "value": "admin.acme.com"},
    ]:
        auth_client.post(f"/programs/{pid}/scope-rules", json=rule)
    chk = lambda h: auth_client.post(f"/programs/{pid}/scope-check", json={"host": h}).json()  # noqa: E731
    assert chk("www.acme.com")["in_scope"] is True
    assert chk("admin.acme.com")["in_scope"] is False
    assert chk("evil.com")["in_scope"] is False
    assert auth_client.post("/programs/999/scope-check", json={"host": "a.com"}).status_code == 404


def test_targets_crud(auth_client):
    pid = mk_program(auth_client)["id"]
    r = auth_client.post(
        f"/programs/{pid}/targets", json={"value": "www.acme.com", "description": "main"}
    )
    assert r.status_code == 201
    tid = r.json()["id"]
    assert (
        auth_client.patch(f"/programs/{pid}/targets/{tid}", json={"description": "x"}).json()[
            "description"
        ]
        == "x"
    )
    assert auth_client.get(f"/programs/{pid}/targets").json()[0]["value"] == "www.acme.com"
    assert auth_client.delete(f"/programs/{pid}/targets/{tid}").status_code == 204


def test_findings_crud_status_severity_payout(auth_client):
    pid = mk_program(auth_client)["id"]
    tid = auth_client.post(f"/programs/{pid}/targets", json={"value": "a.acme.com"}).json()["id"]
    r = auth_client.post(
        f"/programs/{pid}/findings",
        json={"title": "XSS", "severity": "high", "target_id": tid, "description": "# md"},
    )
    assert r.status_code == 201
    f = r.json()
    assert f["status"] == "new" and f["severity"] == "high"
    r = auth_client.patch(
        f"/programs/{pid}/findings/{f['id']}", json={"status": "paid", "payout_cents": 150000}
    )
    assert r.json()["status"] == "paid" and r.json()["payout_cents"] == 150000
    assert (
        auth_client.post(
            f"/programs/{pid}/findings", json={"title": "x", "severity": "huge"}
        ).status_code
        == 422
    )
    assert (
        auth_client.post(
            f"/programs/{pid}/findings", json={"title": "x", "payout_cents": -1}
        ).status_code
        == 422
    )
    assert auth_client.delete(f"/programs/{pid}/findings/{f['id']}").status_code == 204


def test_cross_program_isolation(auth_client):
    p1, p2 = mk_program(auth_client)["id"], mk_program(auth_client, name="Other")["id"]
    t1 = auth_client.post(f"/programs/{p1}/targets", json={"value": "a.com"}).json()["id"]
    assert auth_client.get(f"/programs/{p2}/targets/{t1}").status_code == 404
    r = auth_client.post(f"/programs/{p2}/findings", json={"title": "x", "target_id": t1})
    assert r.status_code == 422


def test_notes_crud_attached_to_finding(auth_client):
    pid = mk_program(auth_client)["id"]
    fid = auth_client.post(f"/programs/{pid}/findings", json={"title": "SQLi"}).json()["id"]
    r = auth_client.post(f"/programs/{pid}/notes", json={"title": "Recon", "body_md": "## hi\n- a"})
    assert r.status_code == 201 and r.json()["finding_id"] is None
    r = auth_client.post(
        f"/programs/{pid}/notes", json={"title": "PoC", "body_md": "`curl`", "finding_id": fid}
    )
    assert r.json()["finding_id"] == fid
    nid = r.json()["id"]
    assert (
        auth_client.patch(f"/programs/{pid}/notes/{nid}", json={"body_md": "new"}).json()["body_md"]
        == "new"
    )
    assert len(auth_client.get(f"/programs/{pid}/notes").json()) == 2
    assert (
        auth_client.post(
            f"/programs/{pid}/notes", json={"title": "x", "finding_id": 999}
        ).status_code
        == 422
    )
    assert auth_client.delete(f"/programs/{pid}/notes/{nid}").status_code == 204


def test_delete_program_cascades(auth_client):
    pid = mk_program(auth_client)["id"]
    auth_client.post(f"/programs/{pid}/targets", json={"value": "a.com"})
    auth_client.post(
        f"/programs/{pid}/scope-rules", json={"action": "in", "type": "domain", "value": "a.com"}
    )
    auth_client.post(f"/programs/{pid}/findings", json={"title": "x"})
    assert auth_client.delete(f"/programs/{pid}").status_code == 204
    assert auth_client.get(f"/programs/{pid}/targets").status_code == 404
