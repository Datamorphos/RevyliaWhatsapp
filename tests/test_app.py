from src.main import app


def test_fastapi_app_exposes_health_route():
    routes = {
        (route.path, tuple(route.methods or ()))
        for route in app.routes
        if hasattr(route, "path")
    }

    assert any(path == "/api/health" and "GET" in methods for path, methods in routes)
