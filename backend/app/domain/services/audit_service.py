"""Domain service for audit log creation.

AuditService encapsulates the business logic of creating audit log records.
This is a domain service (not an application service) because it coordinates
between domain entities and repositories.

Per design.md Â§ Audit Logging (Requirement 8):
- All auth events logged: register, login, logout, refresh, login_failed
- All authz events logged: user deactivation, role changes
- Timestamps use server time (never client-supplied)
- Audit log creation fails gracefully: does not block auth operations
- Failed audit writes logged to structured logs for ops visibility

Traces to: 08-Security-Architecture Â§6 (audit trail integrity)
Traces to: 05-API-Specification Â§2 (audit trail)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from app.domain.entities.audit_log import AuditLog
from app.domain.entities.user import UserRole


if TYPE_CHECKING:
    from app.domain.repositories.audit_log import AuditLogRepository


class AuditService:
    """Domain service for creating and managing audit logs.

    Encapsulates the business logic of creating audit records for
    all state-changing operations. Provides fail-safe semantics:
    audit failures do not block the primary operation.

    Attributes:
        audit_repo: AuditLogRepository for persistence

    Raises:
        ValueError: If invalid parameters provided

    Example:
        ```python
        audit_service = AuditService(audit_repo)
        await audit_service.log_user_registration(
            user_id=user_uuid,
            email="user@example.com",
            ip_address="192.168.1.1",
            request_id="req-123",
        )
        # Audit log created; if creation fails, exception caught
        # and logged by caller (fail-safe)
        ```
    """

    def __init__(self, audit_repo: AuditLogRepository) -> None:
        """Initialize AuditService with repository dependency.

        Args:
            audit_repo: AuditLogRepository for persistence
        """
        self.audit_repo = audit_repo

    async def log_user_registration(
        self,
        user_id: UUID,
        email: str,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log user registration event.

        Creates audit record for user registration (create account).

        Args:
            user_id: ID of the newly created user
            email: User's email address (for context)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
            user_agent: Client User-Agent (optional)

        Returns:
            Created AuditLog record

        Raises:
            RepositoryException: If database error occurs
        """
        after_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "email": email,
            "role": UserRole.VIEWER.value,  # Default role
            "is_active": True,
        })

        audit = AuditLog(
            actor_id=user_id,  # User creating their own account
            actor_role=UserRole.VIEWER.value,
            action="USER_REGISTRATION",
            resource_type="User",
            resource_id=user_id,
            before_state=None,  # Create operation: no before state
            after_state=after_state,
            ip_address=ip_address,
            request_id=request_id,
            user_agent=user_agent,
            success=True,
            failure_reason=None,
            occurred_at=datetime.now(tz=UTC),
        )

        return await self.audit_repo.create(audit)

    async def log_user_login(
        self,
        user_id: UUID,
        user_role: UserRole,
        email: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log successful user login event.

        Creates audit record for successful authentication.

        Args:
            user_id: ID of the user who logged in
            user_role: User's role at login time
            email: User's email (optional, for context)
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
            user_agent: Client User-Agent (optional)

        Returns:
            Created AuditLog record

        Raises:
            RepositoryException: If database error occurs
        """
        after_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "email": email,
            "role": user_role.value,
            "action": "login",
        })

        audit = AuditLog(
            actor_id=user_id,
            actor_role=user_role.value,
            action="USER_LOGIN",
            resource_type="User",
            resource_id=user_id,
            before_state=None,
            after_state=after_state,
            ip_address=ip_address,
            request_id=request_id,
            user_agent=user_agent,
            success=True,
            failure_reason=None,
            occurred_at=datetime.now(tz=UTC),
        )

        return await self.audit_repo.create(audit)

    async def log_login_failed(
        self,
        email: str,
        reason: str,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log failed login attempt.

        Creates audit record for failed authentication (wrong password,
        user not found, user inactive, etc.).

        Note: User ID is None because user may not exist. Email is used
        for context. This enables tracking of attack attempts.

        Args:
            email: Email address attempted (for context)
            reason: Reason for failure (e.g., "invalid_password", "user_inactive")
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
            user_agent: Client User-Agent (optional)

        Returns:
            Created AuditLog record

        Raises:
            RepositoryException: If database error occurs
        """
        after_state = cast("dict[str, object]", {
            "email": email,
            "action": "login_failed",
            "reason": reason,
        })

        audit = AuditLog(
            actor_id=None,  # User not authenticated
            actor_role="unauthenticated",
            action="LOGIN_FAILED",
            resource_type="User",
            resource_id=UUID("00000000-0000-0000-0000-000000000000"),  # Null UUID
            before_state=None,
            after_state=after_state,
            ip_address=ip_address,
            request_id=request_id,
            user_agent=user_agent,
            success=False,
            failure_reason=reason,
            occurred_at=datetime.now(tz=UTC),
        )

        return await self.audit_repo.create(audit)

    async def log_user_logout(
        self,
        user_id: UUID,
        user_role: UserRole,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log user logout event.

        Creates audit record for logout (token revocation).

        Args:
            user_id: ID of the user who logged out
            user_role: User's role at logout time
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
            user_agent: Client User-Agent (optional)

        Returns:
            Created AuditLog record

        Raises:
            RepositoryException: If database error occurs
        """
        after_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "role": user_role.value,
            "action": "logout",
        })

        audit = AuditLog(
            actor_id=user_id,
            actor_role=user_role.value,
            action="USER_LOGOUT",
            resource_type="User",
            resource_id=user_id,
            before_state=None,
            after_state=after_state,
            ip_address=ip_address,
            request_id=request_id,
            user_agent=user_agent,
            success=True,
            failure_reason=None,
            occurred_at=datetime.now(tz=UTC),
        )

        return await self.audit_repo.create(audit)

    async def log_token_refresh(
        self,
        user_id: UUID,
        user_role: UserRole,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log token refresh event.

        Creates audit record for successful token refresh.

        Args:
            user_id: ID of the user who refreshed token
            user_role: User's role at refresh time
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
            user_agent: Client User-Agent (optional)

        Returns:
            Created AuditLog record

        Raises:
            RepositoryException: If database error occurs
        """
        after_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "role": user_role.value,
            "action": "token_refresh",
        })

        audit = AuditLog(
            actor_id=user_id,
            actor_role=user_role.value,
            action="TOKEN_REFRESH",
            resource_type="User",
            resource_id=user_id,
            before_state=None,
            after_state=after_state,
            ip_address=ip_address,
            request_id=request_id,
            user_agent=user_agent,
            success=True,
            failure_reason=None,
            occurred_at=datetime.now(tz=UTC),
        )

        return await self.audit_repo.create(audit)

    async def log_user_role_change(
        self,
        user_id: UUID,
        actor_id: UUID,
        actor_role: UserRole,
        old_role: UserRole,
        new_role: UserRole,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log user role change event.

        Creates audit record for role modification (admin-only operation).

        Args:
            user_id: ID of the user whose role was changed
            actor_id: ID of the admin who performed the change
            actor_role: Admin's role
            old_role: Previous role
            new_role: New role
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
            user_agent: Client User-Agent (optional)

        Returns:
            Created AuditLog record

        Raises:
            RepositoryException: If database error occurs
        """
        before_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "role": old_role.value,
        })

        after_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "role": new_role.value,
        })

        audit = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role.value,
            action="ROLE_CHANGE",
            resource_type="User",
            resource_id=user_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            request_id=request_id,
            user_agent=user_agent,
            success=True,
            failure_reason=None,
            occurred_at=datetime.now(tz=UTC),
        )

        return await self.audit_repo.create(audit)

    async def log_user_deactivation(
        self,
        user_id: UUID,
        actor_id: UUID,
        actor_role: UserRole,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log user deactivation event.

        Creates audit record when admin deactivates a user.

        Args:
            user_id: ID of the user being deactivated
            actor_id: ID of the admin performing deactivation
            actor_role: Admin's role
            ip_address: Client IP address (optional)
            request_id: Request correlation ID (optional)
            user_agent: Client User-Agent (optional)

        Returns:
            Created AuditLog record

        Raises:
            RepositoryException: If database error occurs
        """
        before_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "is_active": True,
        })

        after_state = cast("dict[str, object]", {
            "user_id": str(user_id),
            "is_active": False,
        })

        audit = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role.value,
            action="USER_DEACTIVATION",
            resource_type="User",
            resource_id=user_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            request_id=request_id,
            user_agent=user_agent,
            success=True,
            failure_reason=None,
            occurred_at=datetime.now(tz=UTC),
        )

        return await self.audit_repo.create(audit)

