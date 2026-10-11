from app.main import create_app

# The only routes reachable without a login cookie.
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/auth/status"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
}

DOCS_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def _walk(routes):
    """Yield (path, methods) for every endpoint, across FastAPI versions.

    Newer FastAPI keeps `include_router` results as lazy `_IncludedRouter`
    entries in `app.routes`; they expose flattened `effective_route_contexts`.
    """
    for route in routes:
        if hasattr(route, "effective_route_contexts"):
            for ctx in route.effective_route_contexts():
                methods = getattr(ctx.original_route, "methods", None)
                if methods:
                    yield ctx.path, methods
        elif getattr(route, "methods", None):
            yield route.path, route.methods
        elif getattr(route, "routes", None):
            yield from _walk(route.routes)


def _all_endpoints(app):
    for path, methods in _walk(app.routes):
        for method in sorted(methods - {"HEAD", "OPTIONS"}):
            yield method, path


def _protected_routes(app):
    for method, path in _all_endpoints(app):
        # Framework-generated docs routes are not application endpoints.
        if path in DOCS_PATHS or (method, path) in PUBLIC:
            continue
        yield method, path


def test_every_non_exempt_route_requires_auth(client):
    routes = list(_protected_routes(create_app()))
    assert routes, "no routes discovered"
    for method, path in routes:
        # Path params are dummies; auth must be rejected before they matter.
        url = path.replace("{", "").replace("}", "") if "{" in path else path
        resp = client.request(method, url)
        assert resp.status_code == 401, f"{method} {path} is not protected"


def test_scan_history_and_dashboard_require_auth(client):
    assert client.get("/recon/scans").status_code == 401
    assert client.get("/dashboard/summary").status_code == 401
