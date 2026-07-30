import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_health_endpoint_does_not_leak_resources_in_isolated_process() -> None:
    """Verify that a single FastAPI request path does not leak unclosed resources."""
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "backend")

    script = textwrap.dedent(
        """
        import gc
        import warnings

        from fastapi.testclient import TestClient

        from app.main import create_app

        warnings.simplefilter("error", ResourceWarning)

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 200

            response = client.get("/api/v1/nonexistent")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "not_found"

        gc.collect()
        """
    )

    result = subprocess.run(
        [sys.executable, "-W", "error::ResourceWarning", "-c", script],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise AssertionError(
            "Resource leak detected in isolated subprocess.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )


def test_exception_handler_does_not_leak_resources_in_isolated_process() -> None:
    """Verify exception handler routes do not leak unclosed resources."""
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "backend")

    script = textwrap.dedent(
        """
        import gc
        import warnings

        from fastapi.testclient import TestClient

        from app.main import create_app

        warnings.simplefilter("error", ResourceWarning)

        app = create_app()

        @app.get("/test-resource-leak")
        async def test_resource_leak_route() -> dict[str, str]:
            raise RuntimeError("Test exception handler cleanup")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-resource-leak")
            assert response.status_code == 500
            assert response.json()["error"]["code"] == "internal_server_error"

        gc.collect()
        """
    )

    result = subprocess.run(
        [sys.executable, "-W", "error::ResourceWarning", "-c", script],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise AssertionError(
            "Exception handler resource leak detected in isolated subprocess.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )
