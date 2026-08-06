"""
AuditLogRepository domain interface.

Defines the abstract contract for audit log-related query operations.
AuditLog is append-only (immutable), so the interface only supports
create() and list() operations - no update(), delete(), or soft_delete().

Implementations must not leak infrastructure details (SQLAlchemy, ORM models)
to the Domain layer.

The AuditLogRepository interface is used by Application layer services to
create audit records and query the audit trail. The Domain layer depends on
this interface, not on any concrete PostgreSQL implementation.

Methods:
    - create(entity: AuditLog) -> AuditLog
    - list(skip, limit, sort_by, sort_order, **filters) -> (List[AuditLog], int)
    - list_by_actor(actor_id: UUID, skip, limit) -> (List[AuditLog], int)
    - list_by_resource(resource_type: str, resource_id: UUID, skip, limit)
      -> (List[AuditLog], int)
    - query_by_date_range(start_date, end_date, skip, limit)
      -> (List[AuditLog], int)

No soft-delete support (audit logs are immutable):
    - No delete() method
    - No soft_delete() method
    - No update() method
    - Audit logs persist forever (or until compliance retention policy)

Exception Contract:
    - create() may raise ConstraintViolation if FK or data integrity issues
    - list() returns empty list if no matches found (never raises)
    - All methods may raise RepositoryException on unexpected errors

Traces to: E3.T10 Specification § Requirement R1 (Domain Interfaces)
Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
Traces to: E3.T10 Specification § Requirement R5 (Soft-Delete Semantics - N/A for audit)
Traces to: 03-Architecture §4 (Domain layer)
Traces to: 08-Security-Architecture §6 (Audit trail integrity)
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from app.domain.repositories.base import BaseRepository


if TYPE_CHECKING:
    from app.domain.entities.audit_log import AuditLog


class AuditLogRepository(BaseRepository["AuditLog"]):
    """
    Abstract repository interface for AuditLog entity (immutable queries).

    Manages all audit log persistence operations for the Domain layer.
    Audit logs are append-only and immutable - this interface supports
    only create() and query operations, not modifications.

    Implementations handle database-specific details (SQLAlchemy async,
    efficient querying of immutable logs, etc.) transparently.

    Inherits CRUD methods from BaseRepository[AuditLog]:
        - create(entity: AuditLog) -> AuditLog
        - get_by_id(entity_id: UUID) -> AuditLog
        - list(skip, limit, sort_by, sort_order, **filters)
          -> (List[AuditLog], int)

    Explicitly does NOT inherit (overridden as no-op or error):
        - update(entity_id: UUID, updates: dict) -> RAISES ERROR
        - delete(entity_id: UUID) -> RAISES ERROR (use only in cleanup jobs)

    Adds audit-specific query methods:
        - list_by_actor(actor_id: UUID, skip, limit)
          -> (List[AuditLog], int)
        - list_by_resource(resource_type: str, resource_id: UUID, skip, limit)
          -> (List[AuditLog], int)
        - query_by_date_range(start_date: datetime, end_date: datetime, skip, limit)
          -> (List[AuditLog], int)

    Immutability Enforcement:
        Audit logs cannot be modified or deleted by application code. This is
        enforced at:
        - **ORM layer:** No update() or delete() methods provided
        - **Database layer:** GRANT SELECT, INSERT only to app role
        - **Semantic:** Interface doesn't provide mutation methods

        In rare cases (compliance retention policy enforcement), hard deletion
        via delete() is allowed, but only during scheduled cleanup jobs, never
        during normal application operation.

    Transaction Safety:
        - Methods do NOT commit/rollback transactions
        - Transaction lifecycle is managed by FastAPI dependency injection
        - All repository operations in a request are atomic

    Exception Contract:
        - create(audit_log) raises ConstraintViolation if FK invalid
        - get_by_id(id) raises NotFound if audit log not found
        - list_* methods return empty list if no matches (never raise)
        - update()/delete() raise NotImplementedError (immutable interface)

    Example:
        ```python
        # Service depends on the interface, not implementation
        class AuditService:
            def __init__(self, audit_repo: AuditLogRepository):
                self.audit_repo = audit_repo

            async def record_action(
                self,
                actor_id: UUID,
                action: str,
                resource_type: str,
                resource_id: UUID,
                before_state: dict,
                after_state: dict
            ) -> AuditLog:
                # Create immutable audit record
                audit = await self.audit_repo.create(
                    AuditLog(
                        actor_id=actor_id,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        before_state=before_state,
                        after_state=after_state
                    )
                )
                return audit

            async def query_user_actions(
                self, user_id: UUID, page: int = 1
            ) -> (List[AuditLog], int):
                skip = (page - 1) * 50
                return await self.audit_repo.list_by_actor(
                    user_id, skip=skip, limit=50
                )

            async def query_asset_changes(
                self, asset_id: UUID, page: int = 1
            ) -> (List[AuditLog], int):
                skip = (page - 1) * 50
                return await self.audit_repo.list_by_resource(
                    resource_type="DigitalAsset",
                    resource_id=asset_id,
                    skip=skip,
                    limit=50
                )
        ```

    Traces to: E3.T10 Specification § Requirement R1 (Domain Interfaces)
    Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
    Traces to: E3.T10 Specification § Requirement R5 (NO Soft-Delete for immutable logs)
    Traces to: 03-Architecture §4 (Domain layer)
    Traces to: 08-Security-Architecture §6 (Audit trail integrity)
    Traces to: 04-Database-Design §11 (Audit Strategy)
    """

    @abstractmethod
    async def list_by_actor(
        self,
        actor_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLog], int]:
        """
        Retrieve audit logs filtered by actor (WHO performed the action).

        Fetches all audit records where the actor_id matches the specified UUID.
        This enables querying "What did user X do?" for compliance and forensics.

        Results are sorted chronologically (oldest first) to show action sequence.

        Args:
            actor_id: UUID of the user/actor to retrieve logs for
            skip: Number of logs to skip (pagination offset), default 0
            limit: Maximum logs to return per page, default 20

        Returns:
            Tuple of (logs, total_count) where:
            - logs: List of AuditLog entities for this actor
            - total_count: Total number of audit logs for this actor (for pagination UI)

        Example:
            ```python
            results, total = await audit_repo.list_by_actor(
                actor_id=user_id,
                skip=0,
                limit=50
            )
            # results: list of 50 most recent actions by this user
            # total: total actions by this user
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        Traces to: 08-Security-Architecture §6 (Audit trail queries)
        """
        pass

    @abstractmethod
    async def list_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLog], int]:
        """
        Retrieve audit logs filtered by resource (WHAT was affected).

        Fetches all audit records where the resource_type and resource_id match
        the specified values. This enables querying "What happened to this asset?"
        for forensics and compliance.

        Results are sorted chronologically (oldest first) to show the complete
        history of changes to the resource.

        Args:
            resource_type: Type of resource affected (e.g., 'DigitalAsset', 'Report')
            resource_id: UUID of the resource that was affected
            skip: Number of logs to skip (pagination offset), default 0
            limit: Maximum logs to return per page, default 20

        Returns:
            Tuple of (logs, total_count) where:
            - logs: List of AuditLog entities for this resource
            - total_count: Total number of audit logs for this resource

        Example:
            ```python
            results, total = await audit_repo.list_by_resource(
                resource_type="DigitalAsset",
                resource_id=asset_id,
                skip=0,
                limit=50
            )
            # results: complete history of changes to this asset
            # total: total changes to this asset
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        Traces to: 08-Security-Architecture §6 (Audit trail queries)
        """
        pass

    @abstractmethod
    async def query_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLog], int]:
        """
        Retrieve audit logs within a date range.

        Fetches all audit records where occurred_at falls within the specified
        date range. This enables time-based queries for compliance reports and
        incident investigation.

        Results are sorted chronologically (oldest first within the range).

        Args:
            start_date: Start of date range (inclusive, UTC)
            end_date: End of date range (inclusive, UTC)
            skip: Number of logs to skip (pagination offset), default 0
            limit: Maximum logs to return per page, default 20

        Returns:
            Tuple of (logs, total_count) where:
            - logs: List of AuditLog entities within the date range
            - total_count: Total number of audit logs in the range

        Example:
            ```python
            from datetime import datetime, timedelta, UTC

            start = datetime(2025, 1, 1, tzinfo=UTC)
            end = datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC)

            results, total = await audit_repo.query_by_date_range(
                start_date=start,
                end_date=end,
                skip=0,
                limit=100
            )
            # results: all audit logs from January 2025
            # total: total events in January 2025
            ```

        Traces to: E3.T10 Specification § Requirement R3 (Domain-Specific Queries)
        Traces to: 08-Security-Architecture §6 (Compliance reporting)
        """
        pass
