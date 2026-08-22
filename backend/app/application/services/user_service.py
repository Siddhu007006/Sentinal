"""
User management application service.

Orchestrates user profile updates, role changes, and account deactivation
on top of the User domain entity. Authorization context (the acting user)
is passed in by the route layer; the service enforces the business rules:

- Profile fields (full_name) can be changed by the owner or an admin
- Role changes are admin-only (RoleChangeForbiddenError otherwise)
- Deactivation is admin-only (enforced by the route dependency) and
  revokes all of the user's refresh tokens immediately
- All mutations are audit-logged (fail-safe: audit failures never
  block the primary operation)
- Missing, inactive, or soft-deleted targets raise UserNotFoundError so
  routes can respond 404 without leaking user existence (enumeration
  prevention)

Traces to: Requirement 7 in requirements.md (User Management Routes)
Traces to: design.md § User Management / Authorization Flows
Traces to: 22-Engineering-Backlog E4.T7
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domain.entities.user import User, UserRole
from app.domain.exceptions import NotFound


if TYPE_CHECKING:
    from uuid import UUID

    from app.domain.repositories.refresh_token import RefreshTokenRepository
    from app.domain.repositories.user import UserRepository
    from app.domain.services.audit_service import AuditService


logger = logging.getLogger(__name__)


class UserNotFoundError(Exception):
    """Target user does not exist, is inactive, or is soft-deleted.

    Also raised when a non-admin non-owner actor targets another user,
    so routes respond 404 uniformly (enumeration prevention).
    """


class RoleChangeForbiddenError(Exception):
    """A non-admin actor attempted to change a user's role."""


class UserService:
    """Application service for user management mutations.

    Coordinates User entity mutations with persistence, refresh-token
    revocation, and audit logging. Reads (list/get) stay in the route
    layer; this service owns the write paths.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        audit_service: AuditService,
    ) -> None:
        """Initialize UserService with its dependencies.

        Args:
            user_repo: UserRepository for user persistence
            refresh_token_repo: RefreshTokenRepository for revocation
            audit_service: AuditService for authz event logging
        """
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo
        self.audit_service = audit_service

    async def update_user(
        self,
        actor: User,
        user_id: UUID,
        full_name: str | None = None,
        role: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Update a user's profile and/or role.

        Authorization rules:
        - Owner or admin can update profile fields
        - Only admin can change the role (RoleChangeForbiddenError otherwise)
        - Non-admin non-owner actors get UserNotFoundError (404 semantics)

        Args:
            actor: The authenticated user performing the update
            user_id: ID of the user to update
            full_name: New full name (None = unchanged)
            role: New role string (None = unchanged)
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Returns:
            Updated User entity

        Raises:
            UserNotFoundError: Target missing/inactive/soft-deleted, or
                actor is neither owner nor admin
            RoleChangeForbiddenError: Non-admin attempted a role change
        """
        user = await self._load_target(actor, user_id)

        old_role = user.role
        new_role = UserRole(role) if role is not None else None

        if new_role is not None and actor.role != UserRole.ADMIN:
            raise RoleChangeForbiddenError(
                "Only administrators can change user roles"
            )

        if full_name is not None:
            user = user.update_profile(full_name)
        if new_role is not None and new_role != old_role:
            user = user.update_role(new_role)

        updates: dict[str, object] = {
            "full_name": user.full_name,
            "updated_at": user.updated_at,
        }
        if new_role is not None:
            updates["role"] = user.role.value

        updated = await self.user_repo.update(user.id, updates)

        if new_role is not None and new_role != old_role:
            try:
                await self.audit_service.log_user_role_change(
                    user_id=user.id,
                    actor_id=actor.id,
                    actor_role=actor.role,
                    old_role=old_role,
                    new_role=new_role,
                    ip_address=ip_address,
                    request_id=request_id,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.exception(
                    "Audit log creation failed (non-blocking)",
                    extra={
                        "user_id": user.id,
                        "action": "ROLE_CHANGE",
                        "error": str(e),
                    },
                )

        return updated

    async def deactivate_user(
        self,
        actor: User,
        user_id: UUID,
        ip_address: str | None = None,
        request_id: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Soft-delete a user and revoke all their refresh tokens.

        Deactivation is admin-only; the route enforces this via
        require_role("admin"). Sets is_active=False and deleted_at=<now>
        via the domain entity, then revokes every refresh token so all
        sessions become invalid immediately.

        Args:
            actor: The authenticated admin performing the deactivation
            user_id: ID of the user to deactivate
            ip_address: Client IP address (optional, for audit)
            request_id: Request correlation ID (optional, for audit)
            user_agent: Client User-Agent (optional, for audit)

        Raises:
            UserNotFoundError: Target missing/inactive/soft-deleted
        """
        user = await self._load_target(actor, user_id)

        deactivated = user.deactivate()

        await self.user_repo.update(
            user.id,
            {
                "is_active": False,
                "deleted_at": deactivated.deleted_at,
                "updated_at": deactivated.updated_at,
            },
        )
        await self.refresh_token_repo.revoke_all_for_user(user.id)

        try:
            await self.audit_service.log_user_deactivation(
                user_id=user.id,
                actor_id=actor.id,
                actor_role=actor.role,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.exception(
                "Audit log creation failed (non-blocking)",
                extra={
                    "user_id": user.id,
                    "action": "USER_DEACTIVATION",
                    "error": str(e),
                },
            )

    async def _load_target(self, actor: User, user_id: UUID) -> User:
        """Load the target user and apply enumeration-prevention rules.

        Returns the target user if the actor is admin or owner.

        Raises:
            UserNotFoundError: Target missing or soft-deleted (repo
                NotFound), or actor is neither admin nor owner
        """
        try:
            user = await self.user_repo.get_by_id(user_id)
        except NotFound as e:
            raise UserNotFoundError(f"User not found: {user_id}") from e

        is_admin = actor.role == UserRole.ADMIN
        is_owner = actor.id == user_id

        if not (is_admin or is_owner):
            # 404 (not 403) to prevent user enumeration
            raise UserNotFoundError(f"User not found: {user_id}")

        return user
