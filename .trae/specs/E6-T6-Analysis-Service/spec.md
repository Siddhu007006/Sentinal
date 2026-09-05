# Sentinel E6.T6 - Analysis Service - Product Requirements Document

## Overview
- **Summary**: Complete implementation of the AnalysisService application service that orchestrates analysis request, cancellation, retrieval, and listing operations end-to-end per 22-Engineering-Backlog E6.T6, including comprehensive unit test coverage of all happy and failure paths, fail-safe auditing, correct queue/DB failure semantics, and enforcement of domain lifecycle invariants.
- **Purpose**: Provide the application-level orchestration layer between API routes (E6.T7, not in scope) and the domain/infrastructure layers (AnalyzerRegistry, AnalysisRepository, QueueAdapter, AuditService, DigitalAssetRepository) so that the analysis pipeline has well-defined service-level behavior with explicit error and consistency semantics.
- **Target Users**: Backend API route handlers (E6.T7), worker processes that consume analysis jobs, and operators/auditors who rely on audit trails.

## Goals
- Implement `request_analysis()` with analyzer resolution, asset validation, idempotency for the `(asset_id, analyzer_key, analyzer_version)` triple, pending analysis creation, queue publication (with best-effort cleanup on publish failure), and fail-safe audit creation/idempotent-return logging.
- Implement `cancel_analysis()` using the Analysis domain `cancel()` lifecycle method for pending/running analyses only, persisting the cancelled state and producing a fail-safe cancellation audit record.
- Implement `get_analysis()` returning the analysis or raising the service-level `AnalysisNotFoundError`, mapping the repository `NotFound` cleanly.
- Implement `list_analyses()` with pagination and filters for asset, status, and requester, preserving repository sorting/filtering conventions.
- Ensure all 16+ required unit tests pass with explicit coverage of both happy paths and every required failure/edge path.
- Ruff and MyPy pass on every modified production file.
- Remove unused dependencies introduced during the E6 work (specifically `pypdf` if no production code imports it).

## Non-Goals
- Do not implement or modify E6.T7 (Analysis Route Handlers).
- Do not redesign the domain entity invariants, repository interfaces, queue adapter, or audit service contracts.
- Do not introduce a new outbox/event system or claim "atomic" DB+queue behavior when the implementation does not provide it.
- Do not modify existing integration-test infrastructure fixtures (conftest.py) or unrelated tests/production code.
- Do not redesign unrelated parts of the system.

## Background & Context
Per `docs/22-Engineering-Backlog.md` § E6.T6:
- E6.T6 depends on E6.T2 (Analysis domain entity) and E6.T5 (Analysis Worker/queue infrastructure), which are already in place.
- The Analysis domain entity in `app/domain/entities/analysis.py` already enforces lifecycle invariants via `start()`, `complete()`, `fail()`, and `cancel()` methods.
- `app/domain/repositories/analysis.py` defines `get_completed_analysis()` for idempotency, `list_pending_for_worker()` for the worker FIFO queue, list-by-asset/status filters, and standard CRUD.
- `QueueAdapter` defines `publish(job_type, payload) -> Job` plus claim/ack/nack; queue publish is the established contract for handing jobs to workers.
- `AuditService` already exposes `log_analysis_request(...)` and `log_analysis_cancellation(...)`; the E6 backlog and the existing `UploadService` pattern require audit logging to be fail-safe: audit failures are logged with safe contextual information but never block the primary analysis operation.
- Current state of `app/application/services/analysis_service.py` (baseline read during Specify): all four methods exist, the unit test file contains 16 tests that all pass, Ruff is clean on the file, and MyPy is clean on the file together with related domain files. `list_analyses()` already accepts a `requested_by: UUID | None` filter and passes it through the `filters` dict to the repository `list()` method.
- `pyproject.toml` includes `pypdf>=6.17.0` under `[project.optional-dependencies].dev`; a repository-wide grep found zero `import pypdf` / `from pypdf` usages, making it an unused dependency that E6.T6 must remove per the "Remove unused dependencies introduced during the E6 work" instruction.
- Existing integration tests under `tests/integration/test_analysis_repository.py` and related files produce 13 setup-level `ERROR`s at the `reset_database_tables` fixture because of an unavailable PostgreSQL service (log line "Database unavailable - migrations skipped"). These are pre-existing infrastructure/environment errors, not E6.T6 logic failures; the instruction explicitly asks to "isolate pre-existing infrastructure issues from current changes."

## Functional Requirements
- **FR-1 request_analysis — analyzer & asset validation**:
  Resolve the analyzer via `AnalyzerRegistry.get(analyzer_key)`; raise `AnalyzerNotFoundError` if not registered. Resolve the digital asset via `asset_repo.get_by_id(asset_id)`; raise the repository's `NotFound` (wrapped with matching message) if the asset does not exist.
- **FR-2 request_analysis — idempotency for completed analyses**:
  Call `analysis_repo.get_completed_analysis(asset_id, analyzer_key, analyzer_version)`. If a completed analysis exists, return it **without** calling `analysis_repo.create()` or `queue.publish()`.
- **FR-3 request_analysis — pending creation and queue publish**:
  When no completed analysis exists, create a pending `Analysis` entity (status=`pending`, `analyzer_version` = the version returned by the registered analyzer), persist it, then publish `"analysis.requested"` with `{"analysis_id": str(id)}` via the queue.
- **FR-4 request_analysis — queue-publish failure semantics**:
  If `queue.publish()` raises, perform a best-effort `analysis_repo.delete()` of the newly created pending analysis (wrapped in `contextlib.suppress`), log with safe extras (`analysis_id`, `asset_id`, `analyzer_key`, `analyzer_version`, `error`, `request_id`), then raise `QueuePublicationError` so the system cannot silently leave an unprocessable pending row.
- **FR-5 request_analysis — auditing, fail-safe**:
  For both the idempotent-return path and the new-creation path, call `audit_service.log_analysis_request(...)` with `is_idempotent=True/False` respectively. Any exception from auditing must be caught, logged with `logger.exception(...)` + safe extras (`analysis_id`, `action`, `error`, `request_id`), and the primary operation result returned to the caller unchanged.
- **FR-6 cancel_analysis — lifecycle enforcement via Analysis.cancel()**:
  Load the analysis by ID via the repository (map `NotFound` → `AnalysisNotFoundError`). If the analysis status is not `pending` or `running`, raise `InvalidAnalysisStateError`. Call `analysis.cancel()` (domain lifecycle method, never set status by hand) and persist the resulting `status`, `completed_at`, and `updated_at` fields via the repository `update()`.
- **FR-7 cancel_analysis — auditing, fail-safe**:
  Call `audit_service.log_analysis_cancellation(...)` with `previous_status` equal to the analysis status before cancellation. Any audit exception must be caught, logged with safe extras, and the cancelled analysis must still be returned to the caller.
- **FR-8 get_analysis**:
  Return the result of `analysis_repo.get_by_id(analysis_id)`; map `NotFound` → `AnalysisNotFoundError`.
- **FR-9 list_analyses — pagination & filters**:
  Accept `skip`, `limit`, optional `asset_id` (maps to `digital_asset_id`), optional `status`, optional `requested_by`. Use the existing `AnalysisRepository.list(skip, limit, sort_by, sort_order, **filters)` convention with camelCase→snake_case mapping as already implemented. Return the `(list[Analysis], total_count)` tuple.

## Non-Functional Requirements
- **NFR-1 Clean Architecture layering**: `AnalysisService` depends only on domain-layer interfaces (`AnalysisRepository`, `DigitalAssetRepository`, `QueueAdapter`, `AuditService`, `AnalyzerRegistry`) and imports domain entities/values only; no imports from `app.infrastructure` or `app.models` in the service.
- **NFR-2 Explicit consistency semantics**: The docstring/class comments make it explicit that the DB persist + queue publish pair is **not** claimed to be atomic; queue-publication failure uses best-effort DB cleanup, and the raised `QueuePublicationError` documents that best-effort semantics.
- **NFR-3 Fail-safe audit visibility**: Every swallowed audit exception uses `logger.exception(...)` (not just `logger.error`) and includes the `action` discriminator (`ANALYSIS_REQUEST_CREATED`, `ANALYSIS_REQUEST_IDEMPOTENT`, `ANALYSIS_CANCELLED`) + `analysis_id` + `request_id` for ops tracing.
- **NFR-4 Lint and type correctness**: Ruff `check` and `format` rules, and MyPy strict-mode type checking, pass on every modified Python file without new warnings or suppressions that weaken existing policy.

## Constraints
- **Technical**: Preserve the existing Clean Architecture: API → Application → Domain → Infrastructure. Do not bypass Analysis domain lifecycle methods; do not invent duplicate repository/adapter abstractions.
- **Business**: Idempotency key for analysis is the `(asset_id, analyzer_key, analyzer_version)` triple and applies only to analyses with status `completed`. Terminal analyses (completed/failed/cancelled) are immutable per the Analysis frozen-in-terminal invariant.
- **Dependencies**: Reuse the existing repositories (AnalysisRepository, DigitalAssetRepository), AnalyzerRegistry, QueueAdapter, AuditService, settings, and dependency-injection patterns. Do not add new infrastructure abstractions.
- **Test**: Do not weaken, simplify, or remove any existing test to make suites pass. Add new tests for missing coverage only.

## Assumptions
- The repository `list()` method honors arbitrary keyword filters including `digital_asset_id`, `status`, and `requested_by`, consistent with the `PostgreSQLAnalysisRepository._build_where_clauses` implementation.
- `AnalysisRepository.update(entity_id, updates_dict)` accepts a partial dict of field updates (consistent with current usage in the service and with `PostgreSQLRepository.update`).
- The 13 integration-test setup errors observed in `tests/integration/test_analysis_*` files during the baseline run are environment-level (PostgreSQL unavailable at fixture setup time) and therefore do not indicate logic defects in E6.T6.

## Acceptance Criteria

### AC-1: request_analysis happy paths (create and idempotent return)
- **Type**: `rule`
- **Given**: A registered analyzer, a valid existing digital asset, and no pre-existing completed analysis for the triple.
- **When**: `request_analysis(asset_id, analyzer_key, requested_by, requested_by_role, ...)` is called.
- **Then**: A pending `Analysis` entity is created (repo.create called), `queue.publish("analysis.requested", {"analysis_id": ...})` is called, the audit method is called with `is_idempotent=False`, and the pending analysis is returned. When a second identical call arrives and a completed analysis exists, the existing completed analysis is returned without `repo.create` or `queue.publish`, and the audit is called with `is_idempotent=True`.
- **Pass Condition**: `uv run pytest tests/unit/test_analysis_service.py -v` reports both `test_request_analysis_creates_new_pending_analysis PASSED` and `test_request_analysis_returns_existing_completed_analysis PASSED`.
- **Evidence**: Pytest command output captured in task completion evidence.

### AC-2: request_analysis error paths (unknown analyzer, unknown asset, queue publish failure)
- **Type**: `rule`
- **Given**: An unknown analyzer key, a non-existent asset ID, or a queue adapter that raises on `publish`.
- **When**: `request_analysis(...)` is called with each bad input/scenario.
- **Then**: (a) unknown analyzer raises `AnalyzerNotFoundError`, (b) unknown asset raises `NotFound("Asset not found: …")`, (c) queue publish failure deletes the just-created pending analysis via `repo.delete(id)`, logs an exception-level log line, and raises `QueuePublicationError`.
- **Pass Condition**: `uv run pytest tests/unit/test_analysis_service.py -v` reports `test_request_analysis_raises_for_unknown_analyzer PASSED`, `test_request_analysis_raises_for_unknown_asset PASSED`, and `test_request_analysis_queue_publish_failure_cleans_up_pending_analysis PASSED`.
- **Evidence**: Pytest command output.

### AC-3: request_analysis audit is fail-safe on both paths
- **Type**: `rule`
- **Given**: An `AuditService` whose `log_analysis_request()` raises `RuntimeError("audit db down")`.
- **When**: `request_analysis()` is invoked on (a) the new-creation path and (b) the idempotent-return path.
- **Then**: Both calls succeed (pending analysis returned / existing completed analysis returned), `queue.publish()` is called only in path (a) and never in (b), and no `repo.delete()` occurs.
- **Pass Condition**: `uv run pytest tests/unit/test_analysis_service.py -v` reports `test_request_analysis_audit_failure_does_not_block_primary_operation PASSED` and `test_request_analysis_idempotent_return_audit_failure_does_not_block PASSED`.
- **Evidence**: Pytest command output.

### AC-4: cancel_analysis lifecycle and terminal-state rejection
- **Type**: `rule`
- **Given**: Analyses in `pending`, `running`, and a terminal state (`completed`) plus a non-existent analysis ID.
- **When**: `cancel_analysis(analysis_id, cancelled_by, cancelled_by_role, ...)` is called in each scenario.
- **Then**: (a) pending → cancelled via `analysis.cancel()` and persists; (b) running → cancelled via `analysis.cancel()` and persists; (c) terminal raises `InvalidAnalysisStateError`; (d) missing ID raises `AnalysisNotFoundError`.
- **Pass Condition**: `uv run pytest tests/unit/test_analysis_service.py -v` reports `test_cancel_analysis_from_pending_state PASSED`, `test_cancel_analysis_from_running_state PASSED`, `test_cancel_analysis_raises_for_terminal_state PASSED`, and `test_cancel_analysis_raises_for_unknown_analysis PASSED`.
- **Evidence**: Pytest command output.

### AC-5: cancel_analysis audit is fail-safe
- **Type**: `rule`
- **Given**: An `AuditService` whose `log_analysis_cancellation()` raises `RuntimeError("audit db down")` and a pending analysis.
- **When**: `cancel_analysis()` is called.
- **Then**: The call returns the cancelled analysis, `repo.update()` is called with the cancelled field values, and no exception propagates to the caller.
- **Pass Condition**: `uv run pytest tests/unit/test_analysis_service.py -v` reports `test_cancel_analysis_audit_failure_does_not_block_primary_operation PASSED`.
- **Evidence**: Pytest command output.

### AC-6: get_analysis success and NotFound mapping
- **Type**: `rule`
- **Given**: A valid analysis ID and an unknown analysis ID.
- **When**: `get_analysis(analysis_id)` is called for each.
- **Then**: The valid case returns the analysis entity; the invalid case raises `AnalysisNotFoundError` (not the raw repository `NotFound`).
- **Pass Condition**: `uv run pytest tests/unit/test_analysis_service.py -v` reports `test_get_analysis_returns_analysis PASSED` and `test_get_analysis_raises_for_unknown_analysis PASSED`.
- **Evidence**: Pytest command output.

### AC-7: list_analyses pagination and filters (asset, status, requester)
- **Type**: `rule`
- **Given**: An `AnalysisRepository.list()` mock, a valid asset_id, a status, and a `requested_by` UUID.
- **When**: `list_analyses(skip, limit, asset_id=..., status=..., requested_by=...)` and `list_analyses(skip, limit)` are called.
- **Then**: In the filtered call, the repository `list()` receives `skip`, `limit`, plus keyword arguments `digital_asset_id=asset_id`, `status=status`, and `requested_by=requested_by`; in the unfiltered call, none of these keyword filters are passed. The call returns `(analyses, total_count)` as returned by the repository.
- **Pass Condition**: (a) existing tests `test_list_analyses_with_filters PASSED` and `test_list_analyses_without_filters PASSED` continue to pass; (b) an additional `test_list_analyses_with_requested_by_filter` test is added and passes, asserting that `requested_by` is passed through as the `requested_by` keyword filter to `repo.list`.
- **Evidence**: Pytest command output.

### AC-8: Lint and type correctness on modified files
- **Type**: `rule`
- **Given**: All production files modified for E6.T6.
- **When**: `uv run ruff check <files>` and `uv run mypy <application/service files and changed production files> --ignore-missing-imports` are run.
- **Then**: Both commands exit with status 0 and no new warnings/errors.
- **Pass Condition**: Ruff reports "All checks passed!"; MyPy reports "Success: no issues found in … source files."
- **Evidence**: Command outputs captured during implementation.

### AC-9: Unused dependency pypdf removed
- **Type**: `rule`
- **Given**: `pyproject.toml` baseline includes `pypdf>=6.17.0` under dev dependencies and the repository has zero `import pypdf` / `from pypdf` imports.
- **When**: E6.T6 final diff is inspected.
- **Then**: `pypdf` is no longer listed in any dependency section of `pyproject.toml`.
- **Pass Condition**: `Grep pattern="pypdf" path="pyproject.toml"` returns zero matches.
- **Evidence**: Grep output + final diff inspection.

### AC-10: Architecture fidelity and lifecycle non-bypass
- **Type**: `rubric`
- **Dimension**: Degree to which E6.T6 preserves existing Clean-Architecture boundaries and Analysis domain lifecycle invariants.
- **Scale**: 0-2
- **Anchors**: 0 = service imports infrastructure/ORM models or directly sets `analysis.status="cancelled"` without calling `.cancel()` / `.start()` / etc.; 1 = service depends on domain interfaces and uses lifecycle methods but has one minor layering issue (e.g., passing raw ORM dicts instead of domain types for filters); 2 = service depends exclusively on domain interfaces, maps NotFound→service exception, uses `Analysis.cancel()` for cancellation without manual status assignment, and does not import from `app.infrastructure` or `app.models`.
- **Pass Threshold**: >= 2
- **Evidence**: Static inspection of `app/application/services/analysis_service.py`; MyPy and import-grep results.

### AC-11: Failure-path coverage completeness
- **Type**: `rubric`
- **Dimension**: Coverage of the explicit set of required tests listed in the E6.T6 instruction (21 named scenarios) as passing unit tests.
- **Scale**: 0-2
- **Anchors**: 0 = fewer than 14 required scenarios have a passing test; 1 = 14-19 passing tests but one or two required scenarios are missing (e.g., requester filter list test or audit-failure cancel test); 2 = every explicitly required test scenario has a passing test in `tests/unit/test_analysis_service.py`.
- **Pass Threshold**: >= 2
- **Evidence**: Pytest `-v` output and side-by-side comparison of the instruction's required list vs. test names.

## Open Questions
- None. All named scenarios are covered by existing tests or by one new test (requested_by list filter); `pypdf` usage has been confirmed absent via repository-wide grep. Integration-test setup errors have been identified as environment-level PostgreSQL unavailability and are therefore out of scope for E6.T6 logic remediation.
