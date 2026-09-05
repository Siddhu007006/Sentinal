# Sentinel E6.T6 - Analysis Service - Implementation Plan

## Task 1: Add `list_analyses` requested_by filter unit test
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Add a new unit test `test_list_analyses_with_requested_by_filter` in `tests/unit/test_analysis_service.py` that exercises the `requested_by` filter on `AnalysisService.list_analyses`.
  - Arrange: create a mock `AnalysisRepository.list` returning `([sample_analysis], 1)`; build a valid `requested_by` UUID distinct from the sample asset/analysis IDs.
  - Act: call `await analysis_service.list_analyses(skip=0, limit=10, requested_by=requester_uuid)`.
  - Assert: `repo.list` is called exactly once; `repo.list.call_args.kwargs` contains `"requested_by": requester_uuid` alongside the `skip`/`limit`/`sort_by`/`sort_order` defaults; kwargs must NOT include `digital_asset_id` or `status`.
  - Ensure the new test follows the same async pattern (pytest.mark.asyncio) and fixture conventions as the neighboring list tests.
- **Acceptance Criteria Addressed**: AC-7, AC-10, AC-11
- **Test Requirements**:
  - `rule` TR-1.1: New test passes when run in isolation and alongside the existing list tests; `uv run pytest tests/unit/test_analysis_service.py::test_list_analyses_with_requested_by_filter tests/unit/test_analysis_service.py::test_list_analyses_with_filters tests/unit/test_analysis_service.py::test_list_analyses_without_filters -v` reports 3 PASSED with no FAIL or ERROR.
  - `rule` TR-1.2: Ruff on the test file exits 0; `uv run ruff check tests/unit/test_analysis_service.py` reports "All checks passed!" after the edit.
- **Notes**: The service already accepts `requested_by` and maps it to `filters["requested_by"]`; this task closes the test-coverage gap so the explicit instruction requirement (requester filter) has dedicated test evidence.
- **Completion Evidence**:
  - TR-1.1 PASS: `uv run pytest tests/unit/test_analysis_service.py::test_list_analyses_with_requested_by_filter tests/unit/test_analysis_service.py::test_list_analyses_with_filters tests/unit/test_analysis_service.py::test_list_analyses_without_filters -v` → 3 passed in 0.07s, exit code 0. Exact output: `PASSED tests/unit/test_analysis_service.py::test_list_analyses_without_filters`, `PASSED tests/unit/test_analysis_service.py::test_list_analyses_with_filters`, `PASSED tests/unit/test_analysis_service.py::test_list_analyses_with_requested_by_filter`.
  - TR-1.2 PASS: `uv run ruff check tests/unit/test_analysis_service.py` → `All checks passed!`, exit code 0.

## Task 2: Remove unused `pypdf` dev dependency from pyproject.toml
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: None
- **Description**:
  - Open `pyproject.toml` at the repository root.
  - Locate the dev optional-dependency block (`[project.optional-dependencies] dev = [...]`) and remove the line `"pypdf>=6.17.0",` (index at line ~96).
  - Do not modify any other dependency lines.
  - Verify post-edit: `Grep pattern="pypdf" path="pyproject.toml"` returns zero matches.
- **Acceptance Criteria Addressed**: AC-9
- **Test Requirements**:
  - `rule` TR-2.1: Repository-wide grep for `import pypdf`/`from pypdf` returns zero matches so the removal is provably safe (baseline already confirmed; re-run after the file edit to ensure no accidental pypdf references were introduced).
  - `rule` TR-2.2: `uv run pytest tests/unit/test_analysis_service.py -v` still exits 0 after pyproject.toml is edited, confirming the dep removal does not change runtime behavior of E6.T6 tests.
- **Notes**: Instruction explicitly requires: "Remove unused dependencies introduced during the E6 work. In particular, do not keep pypdf if it is no longer actually used."
- **Completion Evidence**:
  - TR-2.1 PASS: Grep `pattern="pypdf"` `path=pyproject.toml"` → 0 matches. Repository-wide grep `pattern="import pypdf|from pypdf"` across `backend/app` → 0 matches (matches only in planning docs spec.md / tasks.md, not source code).
  - TR-2.2 PASS: `uv run pytest tests/unit/test_analysis_service.py -v` → 17 passed, exit code 0 after the edit; no runtime impact from removing pypdf.

## Task 3: Full verification pass and final diff inspection
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 1, Task 2
- **Description**:
  - 3a. Ruff: run `uv run ruff check app/application/services/analysis_service.py tests/unit/test_analysis_service.py` and also run `uv run ruff check` on any other touched production file (only pyproject.toml otherwise, which has no Python source).
  - 3b. MyPy: run `uv run mypy app/application/services/analysis_service.py app/domain/services/audit_service.py app/domain/entities/analysis.py app/domain/repositories/analysis.py --ignore-missing-imports`.
  - 3c. Targeted E6.T6 unit tests: `uv run pytest tests/unit/test_analysis_service.py -v --tb=short` and confirm 17 tests pass (16 existing + 1 new).
  - 3d. Related analysis-unit regression tests: `uv run pytest tests/unit/test_analysis_entity.py tests/unit/test_analysis_model.py -v --tb=short`.
  - 3e. Worker unit tests (adjacent, not integration): `uv run pytest tests/workers/test_analysis_worker.py -v --tb=short`.
  - 3f. Full E6.T6/analysis unit suite summary: `uv run pytest tests/unit/test_analysis_service.py tests/unit/test_analysis_entity.py tests/unit/test_analysis_model.py tests/workers/test_analysis_worker.py --tb=short`.
  - 3g. Final diff inspection: walk the changed files (`git diff --stat` / `git diff` if repo has a git checkout, otherwise direct file comparison) and confirm no changes outside: (i) `tests/unit/test_analysis_service.py` (adds exactly one new test function, no other edits), (ii) `pyproject.toml` (removes exactly one line, the pypdf entry). Confirm no production logic in `analysis_service.py` was modified.
  - 3h. Re-check integration tests for signal: run `uv run pytest tests/integration/test_analysis_repository.py tests/integration/test_analysis_constraints.py --collect-only 2>&1 | Select-Object -First 40` simply to confirm they still reach test collection (i.e. no module-import errors from E6.T6 file edits); failures at setup due to PostgreSQL unavailable are expected and will be noted as pre-existing environment errors, not E6.T6 regressions.
- **Acceptance Criteria Addressed**: AC-1 through AC-9, AC-10, AC-11
- **Test Requirements**:
  - `rule` TR-3.1: Ruff reports "All checks passed!" on every modified Python file (Step 3a).
  - `rule` TR-3.2: MyPy reports "Success: no issues found in 4 source files" (Step 3b).
  - `rule` TR-3.3: `tests/unit/test_analysis_service.py` reports **exactly 17 passed, 0 failed, 0 error** (Step 3c).
  - `rule` TR-3.4: Related analysis unit suites (Steps 3d, 3e) show no new failures vs. baseline (baseline not run; requirement is "no FAIL result, no ERROR result, and no import/collect errors").
  - `rule` TR-3.5: Full combined run (Step 3f) exits with code 0, all tests PASSED.
  - `rubric` TR-3.6: Diff minimality — dimension: number of additional unintended lines changed outside the two targeted files; scale 0-2; anchors 0 = more than 3 additional non-comment lines changed elsewhere or analysis_service.py production logic touched; 1 = exactly one extra non-comment line elsewhere or one trivial analysis_service.py docstring edit; 2 = diff limited exactly to `tests/unit/test_analysis_service.py` (new test function only) and removal of the pypdf line in `pyproject.toml`; threshold >= 2; evidence: diff inspection captured in Completion Evidence.
  - `rule` TR-3.7: Integration-test collect step (Step 3h) produces zero ModuleNotFoundError / ImportError; any errors are setup-level and explicitly mention database/schema unavailability, confirming E6.T6 edits do not break import paths.
- **Notes**: The E6.T6 completion report must summarize each of the 3a-3h runs with exact pass counts and exit status, and separately list any remaining limitations (the known 13 integration setup-level errors due to PostgreSQL unavailable go here).
- **Completion Evidence**:
  - TR-3.1 PASS: `uv run ruff check app/application/services/analysis_service.py tests/unit/test_analysis_service.py` → "All checks passed!", exit code 0. pyproject.toml is not Python source, so Ruff does not apply.
  - TR-3.2 PASS: `uv run mypy app/application/services/analysis_service.py app/domain/services/audit_service.py app/domain/entities/analysis.py app/domain/repositories/analysis.py --ignore-missing-imports` → "Success: no issues found in 4 source files", exit code 0.
  - TR-3.3 PASS: `uv run pytest tests/unit/test_analysis_service.py -v --tb=short` → **17 passed, 0 failed, 0 error** in 0.30s, exit code 0. Includes new `test_list_analyses_with_requested_by_filter PASSED`.
  - TR-3.4 PASS: 3d entity+model → `115 passed` (0 fail, 0 error). 3e worker → `13 passed` (0 fail, 0 error). No import/collect errors.
  - TR-3.5 PASS: `uv run pytest tests/unit/test_analysis_service.py tests/unit/test_analysis_entity.py tests/unit/test_analysis_model.py tests/workers/test_analysis_worker.py --tb=short` → **145 passed**, exit code 0. Combined count: 17 (service) + 115 (entity+model) + 13 (worker) = 145.
  - TR-3.6 SCORE = 2 (threshold >= 2, PASS): Diff minimality verified. Changed files are *exactly*: (i) `backend/tests/unit/test_analysis_service.py` (added 1 new function `test_list_analyses_with_requested_by_filter` at L619-L650 + trailing newline; no other edits within the file) and (ii) `pyproject.toml` (removed 1 line `"pypdf>=6.17.0",` from dev dependency block; no other dependency edits). Production `analysis_service.py` was NOT modified in this session.
  - TR-3.7 PASS: `uv run pytest tests/integration/test_analysis_repository.py tests/integration/test_analysis_constraints.py --collect-only` → **27 tests collected successfully** with no ModuleNotFoundError/ImportError. Exit code -1 is from `reset_database_tables` fixture setup error ("Database unavailable - migrations skipped") which is environment-level PostgreSQL unavailability, not an E6.T6 source code regression.
