#!/usr/bin/env python3
"""
Comprehensive verification script for Epic 1, 2, 3 acceptance criteria.
Tests all backend infrastructure, core, and database layers independently.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def print_header(text: str) -> None:
    """Print a section header."""
    print(f"\n{CYAN}{'='*70}")
    print(f"{text:^70}")
    print(f"{'='*70}{RESET}\n")


def print_pass(text: str) -> None:
    """Print a passing test."""
    print(f"{GREEN}✓ PASS{RESET} - {text}")


def print_fail(text: str) -> None:
    """Print a failing test."""
    print(f"{RED}✗ FAIL{RESET} - {text}")


def print_test(name: str) -> None:
    """Print a test label."""
    print(f"{YELLOW}{name}{RESET}")


def cmd_exit_code(cmd: list[str], cwd: str = ".") -> tuple[int, str, str]:
    """Execute a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT"
    except Exception as e:
        return 1, "", str(e)


# ============================================================================
# EPIC 1 TESTS
# ============================================================================


def test_e1_t1() -> dict[str, Any]:
    """E1.T1: Backend directory structure."""
    print_test("E1.T1: Backend Directory Structure")
    
    required_dirs = [
        "app/api/v1/routes",
        "app/api/v1/dependencies",
        "app/api/v1/middleware",
        "app/api/v1/exception_handlers",
        "app/application/services",
        "app/application/use_cases",
        "app/application/commands",
        "app/application/queries",
        "app/domain/entities",
        "app/domain/value_objects",
        "app/domain/repositories",
        "app/domain/services",
        "app/domain/events",
        "app/infrastructure/database",
        "app/infrastructure/storage",
        "app/infrastructure/queue",
        "app/infrastructure/ai_providers",
        "app/infrastructure/email",
        "app/infrastructure/logging",
        "app/infrastructure/config",
        "app/workers/analysis_worker",
        "app/workers/retry_worker",
        "app/workers/scheduled",
        "app/analyzers/base",
        "app/analyzers/registry",
        "app/models",
        "app/schemas",
        "app/core",
        "app/utils",
        "tests/unit",
        "tests/integration",
        "tests/api",
        "tests/workers",
        "tests/fixtures",
        "tests/mocks",
        "migrations",
    ]
    
    missing = []
    for d in required_dirs:
        path = Path(d)
        if not path.is_dir():
            missing.append(d)
    
    passed = len(missing) == 0
    if passed:
        print_pass(f"All {len(required_dirs)} required directories exist")
    else:
        print_fail(f"Missing {len(missing)} directories: {', '.join(missing[:3])}...")
    
    return {
        "test": "E1.T1",
        "passed": passed,
        "details": f"{len(required_dirs) - len(missing)}/{len(required_dirs)} dirs found",
    }


def test_e1_t2() -> dict[str, Any]:
    """E1.T2: Python project configuration."""
    print_test("E1.T2: Python Project Configuration")
    
    tests = []
    
    # Test ruff check
    code, stdout, stderr = cmd_exit_code(["ruff", "check", "."], "backend")
    ruff_pass = code == 0
    tests.append(("ruff check", ruff_pass, code))
    
    # Test mypy
    code, _, _ = cmd_exit_code(["mypy", "."], "backend")
    mypy_pass = code == 0
    tests.append(("mypy", mypy_pass, code))
    
    # Test pytest --collect-only
    code, _stdout, _stderr = cmd_exit_code(["pytest", "--collect-only", "-q"], "backend")
    pytest_pass = code == 0
    tests.append(("pytest --collect-only", pytest_pass, code))
    
    all_pass = all(t[1] for t in tests)
    
    for name, passed, code in tests:
        if passed:
            print_pass(f"{name} (exit code {code})")
        else:
            print_fail(f"{name} (exit code {code})")
    
    return {
        "test": "E1.T2",
        "passed": all_pass,
        "details": f"{sum(1 for _, p, _ in tests if p)}/3 tools clean",
    }


def test_e1_t3() -> dict[str, Any]:
    """E1.T3: Environment variable template."""
    print_test("E1.T3: Environment Variable Template")
    
    required_vars = [
        "DATABASE_URL",
        "DATABASE_MIGRATION_URL",
        "POSTGRESQL_SCHEMA_OWNER_PASSWORD",
        "POSTGRESQL_SENTINEL_API_PASSWORD",
        "REDIS_URL",
        "S3_ENDPOINT_URL",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "S3_BUCKET_NAME",
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
        "CORS_ORIGINS",
        "LOG_LEVEL",
        "ENVIRONMENT",
    ]
    
    env_path = Path("../.env.example")
    if not env_path.exists():
        print_fail(".env.example not found")
        return {"test": "E1.T3", "passed": False, "details": "File missing"}
    
    env_content = env_path.read_text(encoding="utf-8", errors="ignore")
    missing = [v for v in required_vars if v not in env_content]
    passed = len(missing) == 0
    
    if passed:
        print_pass(f"All {len(required_vars)} required variables documented")
    else:
        print_fail(f"Missing {len(missing)} variables")
    
    return {
        "test": "E1.T3",
        "passed": passed,
        "details": f"{len(required_vars) - len(missing)}/{len(required_vars)} vars found",
    }


def test_e1_t4() -> dict[str, Any]:
    """E1.T4: Docker Compose configuration."""
    print_test("E1.T4: Docker Compose")
    
    compose_path = Path("../docker-compose.yml")
    passed = compose_path.exists()
    
    if passed:
        print_pass("docker-compose.yml exists")
        # Check for required services
        try:
            content = compose_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            content = ""
        services = ["postgres", "redis", "minio"]
        service_present = all(s in content for s in services)
        if service_present:
            print_pass("All required services defined (PostgreSQL, Redis, MinIO)")
        else:
            print_fail("Missing required services in docker-compose.yml")
            passed = False
    else:
        print_fail("docker-compose.yml not found")
    
    return {"test": "E1.T4", "passed": passed, "details": "File exists" if passed else "File missing"}


def test_e1_t5() -> dict[str, Any]:
    """E1.T5: Pre-commit hooks configuration."""
    print_test("E1.T5: Pre-commit Hooks")
    
    config_path = Path("../.pre-commit-config.yaml")
    passed = config_path.exists()
    
    if passed:
        content = config_path.read_text(encoding="utf-8", errors="ignore")
        hooks = ["ruff", "mypy"]
        hooks_present = all(h in content for h in hooks)
        if hooks_present:
            print_pass(".pre-commit-config.yaml has ruff and mypy hooks")
        else:
            print_fail("Missing expected hooks in .pre-commit-config.yaml")
            passed = False
    else:
        print_fail(".pre-commit-config.yaml not found")
    
    return {"test": "E1.T5", "passed": passed, "details": "File exists" if passed else "File missing"}


def test_e1_t6() -> dict[str, Any]:
    """E1.T6: GitHub Actions CI pipeline."""
    print_test("E1.T6: GitHub Actions CI Pipeline")
    
    ci_path = Path("../.github/workflows/ci.yml")
    passed = ci_path.exists()
    
    if passed:
        content = ci_path.read_text(encoding="utf-8", errors="ignore")
        # Check for job definitions
        has_jobs = "jobs:" in content
        if has_jobs:
            print_pass(".github/workflows/ci.yml exists with jobs defined")
        else:
            print_fail("CI file exists but jobs not defined")
            passed = False
    else:
        print_fail(".github/workflows/ci.yml not found")
    
    return {"test": "E1.T6", "passed": passed, "details": "File exists" if passed else "File missing"}


def test_e1_t7() -> dict[str, Any]:
    """E1.T7: Repository README."""
    print_test("E1.T7: Repository README")
    
    readme_path = Path("../README.md")
    passed = readme_path.exists()
    
    if passed:
        content = readme_path.read_text(encoding="utf-8", errors="ignore")
        sections = ["Quick Start", "Prerequisites", "Contributing", "Documentation", "Project Structure"]
        missing_sections = [s for s in sections if s not in content]
        if not missing_sections:
            print_pass("README.md has all required sections")
        else:
            print_fail(f"README.md missing sections: {', '.join(missing_sections)}")
            passed = False
    else:
        print_fail("README.md not found")
    
    return {"test": "E1.T7", "passed": passed, "details": "File exists" if passed else "File missing"}


# ============================================================================
# EPIC 2 TESTS
# ============================================================================


def test_e2_t1() -> dict[str, Any]:
    """E2.T1: Settings management."""
    print_test("E2.T1: Settings Management")
    
    settings_path = Path("backend/app/core/settings.py")
    passed = settings_path.exists()
    
    if passed:
        print_pass("app/core/settings.py exists")
        # Try to import
        code, _stdout, _stderr = cmd_exit_code(
            ["python", "-c", "from app.core.settings import Settings; Settings()"],
            "backend",
        )
        if code == 0:
            print_pass("Settings can be imported and instantiated")
        else:
            print_fail(f"Settings instantiation failed (exit code {code})")
            passed = False
    else:
        print_fail("app/core/settings.py not found")
    
    return {"test": "E2.T1", "passed": passed, "details": "File exists and importable" if passed else "File missing or import failed"}


def test_e2_t2() -> dict[str, Any]:
    """E2.T2: FastAPI app factory."""
    print_test("E2.T2: FastAPI Application Factory")
    
    main_path = Path("backend/app/main.py")
    passed = main_path.exists()
    
    if passed:
        print_pass("app/main.py exists")
        code, stdout, _stderr = cmd_exit_code(
            ["python", "-c", "from app.main import create_app; app = create_app(); print('OK')"],
            "backend",
        )
        if code == 0 and "OK" in stdout:
            print_pass("create_app() factory works")
        else:
            print_fail(f"create_app() failed (exit code {code})")
            passed = False
    else:
        print_fail("app/main.py not found")
    
    return {"test": "E2.T2", "passed": passed, "details": "File exists and factory works" if passed else "File missing or factory failed"}


def test_e2_t3() -> dict[str, Any]:
    """E2.T3: Structured logging."""
    print_test("E2.T3: Structured Logging")
    
    logging_path = Path("backend/app/infrastructure/logging")
    passed = logging_path.is_dir()
    
    if passed:
        print_pass("app/infrastructure/logging/ directory exists")
        # Check for logging configuration
        init_file = logging_path / "__init__.py"
        if init_file.exists():
            print_pass("Logging module has __init__.py")
        else:
            print_fail("Logging module missing __init__.py")
            passed = False
    else:
        print_fail("app/infrastructure/logging/ not found")
    
    return {"test": "E2.T3", "passed": passed, "details": "Directory exists" if passed else "Directory missing"}


def test_e2_t4() -> dict[str, Any]:
    """E2.T4: Request ID middleware."""
    print_test("E2.T4: Request ID Middleware")
    
    middleware_path = Path("backend/app/api/v1/middleware/request_id.py")
    passed = middleware_path.exists()
    
    if passed:
        print_pass("app/api/v1/middleware/request_id.py exists")
    else:
        print_fail("app/api/v1/middleware/request_id.py not found")
    
    return {"test": "E2.T4", "passed": passed, "details": "File exists" if passed else "File missing"}


def test_e2_t5() -> dict[str, Any]:
    """E2.T5: Exception handlers."""
    print_test("E2.T5: Exception Handlers")
    
    handlers_dir = Path("backend/app/api/v1/exception_handlers")
    passed = handlers_dir.is_dir()
    
    if passed:
        print_pass("app/api/v1/exception_handlers/ directory exists")
        # Check for handler files
        init_file = handlers_dir / "__init__.py"
        if init_file.exists():
            print_pass("Exception handlers module initialized")
        else:
            print_fail("Exception handlers missing __init__.py")
            passed = False
    else:
        print_fail("app/api/v1/exception_handlers/ not found")
    
    return {"test": "E2.T5", "passed": passed, "details": "Directory exists" if passed else "Directory missing"}


def test_e2_t6() -> dict[str, Any]:
    """E2.T6: CORS middleware."""
    print_test("E2.T6: CORS Middleware")
    
    main_path = Path("app/main.py")
    passed = main_path.exists()
    
    if passed:
        content = main_path.read_text()
        if "CORS" in content or "cors" in content:
            print_pass("CORS configuration found in app/main.py")
        else:
            print_fail("CORS not configured in app/main.py")
            passed = False
    else:
        print_fail("app/main.py not found")
    
    return {"test": "E2.T6", "passed": passed, "details": "CORS configured" if passed else "CORS not found"}


def test_e2_t7() -> dict[str, Any]:
    """E2.T7: Rate limiting middleware."""
    print_test("E2.T7: Rate Limiting Middleware")
    
    # Check for rate limiting implementation
    middleware_dir = Path("app/api/v1/middleware")
    rate_limit_file = middleware_dir / "rate_limit.py"
    passed = rate_limit_file.exists()
    
    if not passed:
        # Alternative: check in main.py
        main_path = Path("app/main.py")
        if main_path.exists():
            content = main_path.read_text()
            if "rate" in content.lower():
                print_pass("Rate limiting reference found in app/main.py")
                passed = True
    
    if passed:
        print_pass("Rate limiting middleware exists")
    else:
        print_fail("Rate limiting middleware not found")
    
    return {"test": "E2.T7", "passed": passed, "details": "Rate limiting configured" if passed else "Rate limiting not found"}


def test_e2_t8() -> dict[str, Any]:
    """E2.T8: Health check endpoint."""
    print_test("E2.T8: Health Check Endpoint")
    
    routes_dir = Path("app/api/v1/routes")
    health_file = routes_dir / "health.py"
    passed = health_file.exists()
    
    if passed:
        print_pass("app/api/v1/routes/health.py exists")
    else:
        # Alternative: check main.py
        main_path = Path("app/main.py")
        if main_path.exists():
            content = main_path.read_text()
            if "/health" in content:
                print_pass("Health endpoint referenced in app/main.py")
                passed = True
        else:
            print_fail("app/api/v1/routes/health.py not found")
    
    return {"test": "E2.T8", "passed": passed, "details": "Health endpoint defined" if passed else "Health endpoint not found"}


def test_e2_t9() -> dict[str, Any]:
    """E2.T9: Base Pydantic schemas."""
    print_test("E2.T9: Base Pydantic Schemas")
    
    schemas_dir = Path("app/schemas")
    passed = schemas_dir.is_dir()
    
    if passed:
        content_str = ""
        for py_file in schemas_dir.glob("*.py"):
            content_str += py_file.read_text()
        
        schemas = ["PaginatedResponse", "ErrorResponse", "TimestampMixin"]
        missing = [s for s in schemas if s not in content_str]
        
        if not missing:
            print_pass(f"All required schemas found: {', '.join(schemas)}")
        else:
            print_fail(f"Missing schemas: {', '.join(missing)}")
            passed = False
    else:
        print_fail("app/schemas/ directory not found")
    
    return {"test": "E2.T9", "passed": passed, "details": "Base schemas defined" if passed else "Schemas missing"}


# ============================================================================
# EPIC 3 TESTS
# ============================================================================


def test_e3_t1() -> dict[str, Any]:
    """E3.T1: Database session management."""
    print_test("E3.T1: Database Session Management")
    
    session_path = Path("app/infrastructure/database/session.py")
    passed = session_path.exists()
    
    if passed:
        print_pass("app/infrastructure/database/session.py exists")
    else:
        print_fail("app/infrastructure/database/session.py not found")
    
    return {"test": "E3.T1", "passed": passed, "details": "File exists" if passed else "File missing"}


def test_e3_t2() -> dict[str, Any]:
    """E3.T2: Alembic configuration."""
    print_test("E3.T2: Alembic Configuration")
    
    alembic_ini = Path("alembic.ini")
    migrations_dir = Path("migrations")
    passed = alembic_ini.exists() and migrations_dir.is_dir()
    
    if passed:
        print_pass("alembic.ini and migrations/ directory exist")
    else:
        print_fail("Alembic not properly configured")
    
    return {"test": "E3.T2", "passed": passed, "details": "Alembic configured" if passed else "Alembic missing"}


def test_e3_t3_to_t9() -> dict[str, Any]:
    """E3.T3-T9: ORM models."""
    print_test("E3.T3-E3.T9: ORM Models")
    
    models_dir = Path("app/models")
    required_models = [
        "user.py",
        "upload.py",
        "digital_asset.py",
        "analysis.py",
        "report.py",
        "audit_log.py",
        "refresh_token.py",
    ]
    
    missing = []
    for model_file in required_models:
        if not (models_dir / model_file).exists():
            missing.append(model_file)
    
    passed = len(missing) == 0
    
    if passed:
        print_pass(f"All {len(required_models)} ORM models exist")
    else:
        print_fail(f"Missing {len(missing)} ORM models: {', '.join(missing)}")
    
    return {
        "test": "E3.T3-E3.T9",
        "passed": passed,
        "details": f"{len(required_models) - len(missing)}/{len(required_models)} models found",
    }


def test_e3_t10() -> dict[str, Any]:
    """E3.T10: Domain repository interfaces."""
    print_test("E3.T10: Domain Repository Interfaces")
    
    repos_dir = Path("app/domain/repositories")
    required_repos = [
        "user_repository.py",
        "upload_repository.py",
        "digital_asset_repository.py",
        "analysis_repository.py",
        "report_repository.py",
        "audit_log_repository.py",
    ]
    
    missing = []
    for repo_file in required_repos:
        if not (repos_dir / repo_file).exists():
            missing.append(repo_file)
    
    passed = len(missing) == 0
    
    if passed:
        print_pass(f"All {len(required_repos)} domain repository interfaces exist")
    else:
        print_fail(f"Missing {len(missing)} repository interfaces: {', '.join(missing)}")
    
    return {
        "test": "E3.T10",
        "passed": passed,
        "details": f"{len(required_repos) - len(missing)}/{len(required_repos)} repos found",
    }


def test_e3_t11() -> dict[str, Any]:
    """E3.T11: PostgreSQL repository implementations."""
    print_test("E3.T11: PostgreSQL Repository Implementations")
    
    repos_dir = Path("app/infrastructure/database/repositories")
    required_impls = [
        "user_repository.py",
        "upload_repository.py",
        "digital_asset_repository.py",
        "analysis_repository.py",
        "report_repository.py",
        "audit_log_repository.py",
    ]
    
    missing = []
    for impl_file in required_impls:
        if not (repos_dir / impl_file).exists():
            missing.append(impl_file)
    
    passed = len(missing) == 0
    
    if passed:
        print_pass(f"All {len(required_impls)} PostgreSQL repository implementations exist")
    else:
        print_fail(f"Missing {len(missing)} implementations: {', '.join(missing)}")
    
    return {
        "test": "E3.T11",
        "passed": passed,
        "details": f"{len(required_impls) - len(missing)}/{len(required_impls)} impls found",
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main() -> None:
    """Run all verification tests."""
    print_header("EPIC 1, 2, 3 INDEPENDENT VERIFICATION")
    
    all_results: list[dict[str, Any]] = []
    
    # EPIC 1
    print_header("EPIC 1: Repository Foundation")
    all_results.append(test_e1_t1())
    all_results.append(test_e1_t2())
    all_results.append(test_e1_t3())
    all_results.append(test_e1_t4())
    all_results.append(test_e1_t5())
    all_results.append(test_e1_t6())
    all_results.append(test_e1_t7())
    
    # EPIC 2
    print_header("EPIC 2: Backend Core")
    all_results.append(test_e2_t1())
    all_results.append(test_e2_t2())
    all_results.append(test_e2_t3())
    all_results.append(test_e2_t4())
    all_results.append(test_e2_t5())
    all_results.append(test_e2_t6())
    all_results.append(test_e2_t7())
    all_results.append(test_e2_t8())
    all_results.append(test_e2_t9())
    
    # EPIC 3
    print_header("EPIC 3: Database & Persistence")
    all_results.append(test_e3_t1())
    all_results.append(test_e3_t2())
    all_results.append(test_e3_t3_to_t9())
    all_results.append(test_e3_t10())
    all_results.append(test_e3_t11())
    
    # Summary
    print_header("SUMMARY")
    passed_count = sum(1 for r in all_results if r["passed"])
    total_count = len(all_results)
    
    print(f"Total Tests: {total_count}")
    print(f"Passed: {GREEN}{passed_count}{RESET}")
    print(f"Failed: {RED}{total_count - passed_count}{RESET}")
    
    if passed_count == total_count:
        print(f"\n{GREEN}ALL TESTS PASSED ✓{RESET}")
    else:
        print(f"\n{RED}{total_count - passed_count} TESTS FAILED{RESET}")
        for result in all_results:
            if not result["passed"]:
                print(f"  - {result['test']}")
    
    # Detailed report
    print_header("DETAILED RESULTS")
    for result in all_results:
        status = f"{GREEN}PASS{RESET}" if result["passed"] else f"{RED}FAIL{RESET}"
        print(f"{result['test']:12} [{status}] {result['details']}")


if __name__ == "__main__":
    main()
