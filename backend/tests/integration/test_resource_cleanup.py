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
    # Provide minimal DB env vars so Settings validation succeeds in subprocess.
    # The subprocess only imports app and does small TestClient requests; no
    # real DB connection is required here. Use lightweight SQLite memory URIs
    # to satisfy pydantic validation of `DatabaseSettings`.
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["DATABASE_MIGRATION_URL"] = "sqlite:///:memory:"
    # Provide minimal storage and security env vars required by Settings
    env["S3_ENDPOINT_URL"] = "http://localhost:9000"
    env["S3_BUCKET_NAME"] = "test-bucket"
    env["S3_ACCESS_KEY"] = "test-access-key"
    env["S3_SECRET_KEY"] = "test-secret-key"  # noqa: S105
    env["JWT_SECRET_KEY"] = "test-secret-key-which-is-long-enough"  # noqa: S105
    env["REDIS_URL"] = "redis://localhost:6379/0"

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

    result = subprocess.run(  # noqa: S603
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
    # Provide minimal DB env vars so Settings validation succeeds in subprocess.
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["DATABASE_MIGRATION_URL"] = "sqlite:///:memory:"
    env["S3_ENDPOINT_URL"] = "http://localhost:9000"
    env["S3_BUCKET_NAME"] = "test-bucket"
    env["S3_ACCESS_KEY"] = "test-access-key"
    env["S3_SECRET_KEY"] = "test-secret-key"  # noqa: S105
    env["JWT_SECRET_KEY"] = "test-secret-key-which-is-long-enough"  # noqa: S105
    env["REDIS_URL"] = "redis://localhost:6379/0"

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

    result = subprocess.run(  # noqa: S603
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
