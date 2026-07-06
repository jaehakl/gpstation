from app.main import app


def test_launcher_routes_replace_legacy_routes():
    paths = {route.path for route in app.routes}
    legacy_prefix = "/v1/" + "work" + "ers"

    assert "/v1/launchers" in paths
    assert "/v1/launchers/control" in paths
    assert legacy_prefix not in paths
    assert f"{legacy_prefix}/control" not in paths
