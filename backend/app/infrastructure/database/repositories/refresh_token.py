"""
PostgreSQL RefreshToken repository implementation.

Server-side refresh token store for session management and revocation.
Tokens are immutable after creation; only revoke() modifies (sets is_revoked).
delete_expired() hard-deletes expired tokens for cleanup.

Traces to: E3.T11 Specification § Requirement R1-R9
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID  # noqa: TC003

from sqlalchemy import and_, desc, func, select, update

from app.domain.repositories.refresh_token import RefreshTokenRepository
from app.infrastructure.database.repositories.base import PostgreSQLRepository
from app.infrastructure.database.repositories.exceptions import map_db_exception
from app.models.refresh_token import RefreshToken as RefreshTokenORM


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.entities.refresh_token import (
        RefreshToken as RefreshTokenEntity,  # noqa: F401
    )


class PostgreSQLRefreshTokenRepository(
    PostgreSQLRepository["RefreshTokenEntity"], RefreshTokenRepository
):
    """PostgreSQL repository for RefreshToken entity (session management)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._model_class = RefreshTokenORM
        self._entity_name = "RefreshToken"

    def _to_orm(self, entity: Any) -> RefreshTokenORM:  # noqa: ANN401
        """Convert domain entity to ORM model."""
        return RefreshTokenORM(
            id=entity.id,
            user_id=entity.user_id,
            jti=entity.jti,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
            is_revoked=entity.is_revoked,
            user_agent=entity.user_agent,
            ip_address=entity.ip_address,
            revoked_at=entity.revoked_at,
        )

    def _to_domain(self, orm_obj: RefreshTokenORM) -> Any:  # noqa: ANN401
        """Convert ORM model to domain entity."""
        from app.domain.entities.refresh_token import RefreshToken

        return RefreshToken(
            id=orm_obj.id,
            user_id=orm_obj.user_id,
            jti=orm_obj.jti,
            token_hash=orm_obj.token_hash,
            expires_at=orm_obj.expires_at,
            is_revoked=orm_obj.is_revoked,
            user_agent=orm_obj.user_agent,
            ip_address=orm_obj.ip_address,
            revoked_at=orm_obj.revoked_at,
            created_at=orm_obj.created_at,
        )

    def _build_where_clauses(self, **filters: object) -> list[Any]:
        """Build WHERE clauses from filter arguments."""
        clauses: list[Any] = []
        if "user_id" in filters:
            clauses.append(RefreshTokenORM.user_id == filters["user_id"])
        if "is_revoked" in filters:
            clauses.append(RefreshTokenORM.is_revoked == filters["is_revoked"])
        if "token_hash" in filters:
            clauses.append(RefreshTokenORM.token_hash == filters["token_hash"])
        return clauses

    def _apply_eager_loading(self, stmt: Any) -> Any:  # noqa: ANN401
        """Apply eager loading for relationships (none for RefreshToken)."""
        return stmt

    def _is_soft_delete_entity(self) -> bool:
        """RefreshToken uses hard delete (tokens are immutable, can only revoke)."""
        return False

    async def get_by_hash(self, token_hash: str) -> Any | None:  # noqa: ANN401
        """Retrieve refresh token by SHA-256 hash."""
        try:
            stmt = select(RefreshTokenORM).where(
                RefreshTokenORM.token_hash == token_hash
            )
            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                return None
            return self._to_domain(orm_obj)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def revoke(self, token_id: UUID) -> Any:  # noqa: ANN401
        """Revoke a refresh token atomically (set is_revoked=True, revoked_at=now()).

        Uses atomic conditional UPDATE to prevent concurrent reuse:
        UPDATE ... SET is_revoked=TRUE WHERE id=$1 AND is_revoked=FALSE

        If the token was already revoked by a concurrent request, returns None
        to signal that revocation was not performed (was already revoked).
        This enables the caller to detect concurrent token rotation attempts.
        """
        try:
            # Atomic conditional UPDATE: only succeed if is_revoked=False
            now = datetime.now(tz=UTC)
            stmt = (
                update(RefreshTokenORM)
                .where(
                    and_(
                        RefreshTokenORM.id == token_id,
                        RefreshTokenORM.is_revoked == False,  # noqa: E712
                    )
                )
                .values(
                    is_revoked=True,
                    revoked_at=now,
                    updated_at=now,
                )
                .returning(RefreshTokenORM)
            )

            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()

            # If no rows returned, token was already revoked
            if orm_obj is None:
                return None

            return self._to_domain(orm_obj)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def list_active_by_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Any], int]:
        """Retrieve active (non-revoked, non-expired) tokens for a user."""
        try:
            now = datetime.now(tz=UTC)

            stmt = select(RefreshTokenORM).where(
                and_(
                    RefreshTokenORM.user_id == user_id,
                    RefreshTokenORM.is_revoked == False,  # noqa: E712
                    RefreshTokenORM.expires_at > now,
                )
            )

            # Calculate total count
            count_stmt = (
                select(func.count())
                .select_from(RefreshTokenORM)
                .where(
                    and_(
                        RefreshTokenORM.user_id == user_id,
                        RefreshTokenORM.is_revoked == False,  # noqa: E712
                        RefreshTokenORM.expires_at > now,
                    )
                )
            )
            total = await self.session.scalar(count_stmt)
            if total is None:
                total = 0

            # Apply sorting (most recent first)
            stmt = stmt.order_by(desc(RefreshTokenORM.created_at))
            stmt = stmt.offset(skip).limit(limit)

            results = await self.session.scalars(stmt)
            return ([self._to_domain(orm) for orm in results], total)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def delete_expired(self) -> int:
        """Hard-delete expired, non-revoked tokens (cleanup operation)."""
        try:
            now = datetime.now(tz=UTC)

            # Count tokens to delete
            count_stmt = (
                select(func.count())
                .select_from(RefreshTokenORM)
                .where(
                    and_(
                        RefreshTokenORM.is_revoked == False,  # noqa: E712
                        RefreshTokenORM.expires_at < now,
                    )
                )
            )
            deleted_count = await self.session.scalar(count_stmt)
            if deleted_count is None:
                deleted_count = 0

            # Delete expired tokens
            stmt = select(RefreshTokenORM).where(
                and_(
                    RefreshTokenORM.is_revoked == False,  # noqa: E712
                    RefreshTokenORM.expires_at < now,
                )
            )
            results = await self.session.scalars(stmt)
            for orm_obj in results:
                await self.session.delete(orm_obj)

            await self.session.flush()
            return deleted_count
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def get_by_jti(self, jti: str) -> Any | None:  # noqa: ANN401
        """Retrieve refresh token by JTI (JWT ID claim).

        The JTI is stored in the jti column and used to track token identity
        across rotations for revocation purposes.
        """
        try:
            stmt = select(RefreshTokenORM).where(RefreshTokenORM.jti == jti)
            orm_obj = await self.session.scalar(stmt)
            if not orm_obj:
                return None
            return self._to_domain(orm_obj)
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def atomic_revoke_by_jti(self, jti: str) -> bool:
        """Atomically revoke a token by JTI (for token rotation concurrency).

        Single atomic UPDATE statement prevents race condition where two concurrent
        refresh requests both try to revoke the same old token and both create
        new replacement tokens.

        UPDATE user_refresh_tokens
        SET is_revoked=TRUE, revoked_at=now()
        WHERE jti=$1 AND is_revoked=FALSE
        RETURNING *

        Returns True if this request successfully revoked the token
        (was not yet revoked).
        Returns False if the token was already revoked by a concurrent request.

        Args:
            jti: JWT ID of token to revoke

        Returns:
            True if revoked successfully (this request won the race)
            False if already revoked (concurrent request won the race)
        """
        try:
            now = datetime.now(tz=UTC)
            stmt = (
                update(RefreshTokenORM)
                .where(
                    and_(
                        RefreshTokenORM.jti == jti,
                        RefreshTokenORM.is_revoked == False,  # noqa: E712
                    )
                )
                .values(
                    is_revoked=True,
                    revoked_at=now,
                    updated_at=now,
                )
                .returning(RefreshTokenORM)
            )

            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()

            # If no rows returned, token was already revoked by concurrent request
            return orm_obj is not None
        except Exception as exc:
            raise map_db_exception(exc) from exc

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        """Revoke all active refresh tokens for a user (logout all devices)."""
        try:
            now = datetime.now(tz=UTC)

            # Find all active tokens for user
            stmt = select(RefreshTokenORM).where(
                and_(
                    RefreshTokenORM.user_id == user_id,
                    RefreshTokenORM.is_revoked == False,  # noqa: E712
                    RefreshTokenORM.expires_at > now,
                )
            )
            results = await self.session.scalars(stmt)

            # Revoke all
            revoked_count = 0
            for orm_obj in results:
                orm_obj.is_revoked = True
                orm_obj.revoked_at = datetime.now(tz=UTC)
                revoked_count += 1

            await self.session.flush()
            return revoked_count
        except Exception as exc:
            raise map_db_exception(exc) from exc
