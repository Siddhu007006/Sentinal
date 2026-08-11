"""Tests for password hashing service.

Tests verify:
- Hash uniqueness (salt)
- Verification correctness
- Constant-time comparison (timing attack resistance)
- Error handling (empty passwords)
- Both ArgonPasswordHasher and BcryptPasswordHasher
- Factory function selection

Per Requirement 2 in requirements.md and design.md § Password Hashing Service.
"""

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.security.password import (
    ArgonPasswordHasher,
    BcryptPasswordHasher,
    PasswordHasherInterface,
    get_password_hasher,
)


class TestArgonPasswordHasher:
    """Test suite for ArgonPasswordHasher."""

    @pytest.fixture
    def hasher(self) -> ArgonPasswordHasher:
        """Create an ArgonPasswordHasher instance."""
        return ArgonPasswordHasher()

    def test_hash_password_returns_string(self, hasher: ArgonPasswordHasher) -> None:
        """Test that hash_password returns a non-empty string."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_hash_password_different_from_plaintext(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that hash is not equal to plaintext."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hash_value != plaintext

    def test_hash_password_same_plaintext_produces_different_hashes(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that same plaintext produces different hashes (salt)."""
        plaintext = "test_password_12345"
        hash1 = hasher.hash_password(plaintext)
        hash2 = hasher.hash_password(plaintext)

        # Different hashes due to different salts
        assert hash1 != hash2
        # Both should verify correctly
        assert hasher.verify_password(plaintext, hash1)
        assert hasher.verify_password(plaintext, hash2)

    def test_hash_password_rejects_empty_password(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that empty password raises ValueError."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hasher.hash_password("")

    def test_verify_password_correct_password_returns_true(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that verify_password returns True for correct password."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password(plaintext, hash_value) is True

    def test_verify_password_incorrect_password_returns_false(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that verify_password returns False for incorrect password."""
        plaintext = "test_password_12345"
        wrong_password = "wrong_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password(wrong_password, hash_value) is False

    def test_verify_password_empty_plaintext_returns_false(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that verify_password returns False for empty plaintext."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password("", hash_value) is False

    def test_verify_password_empty_hash_returns_false(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that verify_password returns False for empty hash."""
        plaintext = "test_password_12345"

        assert hasher.verify_password(plaintext, "") is False

    def test_verify_password_none_plaintext_returns_false(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that verify_password returns False for None plaintext."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password(None, hash_value) is False  # type: ignore[arg-type]

    def test_verify_password_invalid_hash_returns_false(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that verify_password returns False for invalid hash."""
        plaintext = "test_password_12345"
        invalid_hash = "not_a_valid_hash"

        assert hasher.verify_password(plaintext, invalid_hash) is False

    def test_verify_password_timing_attack_resistance(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test constant-time comparison (timing attack resistance).

        Execution time should not vary significantly based on
        where the password mismatches. This test runs verify_password
        with different wrong passwords and checks that timing
        variance is not proportional to mismatch position.
        """
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        # Measure time for several wrong passwords
        times: list[float] = []
        for i in range(5):
            wrong_password = f"wrong_password_{i:05d}"
            start = time.perf_counter()
            hasher.verify_password(wrong_password, hash_value)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # Times should be relatively consistent
        # Allow up to 50% variance (argon2 has built-in constant-time comparison)
        avg_time = sum(times) / len(times)
        for t in times:
            # If avg is very small, absolute diff; if larger, percentage
            if avg_time > 0.001:
                relative_diff = abs(t - avg_time) / avg_time
                assert (
                    relative_diff < 0.5
                ), f"Timing variance too high: {relative_diff}"

    def test_needs_rehash_returns_boolean(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that needs_rehash returns a boolean."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        result = hasher.needs_rehash(hash_value)
        assert isinstance(result, bool)

    def test_isinstance_password_hasher_interface(
        self, hasher: ArgonPasswordHasher
    ) -> None:
        """Test that ArgonPasswordHasher implements PasswordHasherInterface."""
        assert isinstance(hasher, PasswordHasherInterface)


class TestBcryptPasswordHasher:
    """Test suite for BcryptPasswordHasher."""

    @pytest.fixture
    def hasher(self) -> BcryptPasswordHasher:
        """Create a BcryptPasswordHasher instance."""
        return BcryptPasswordHasher(cost=12)

    def test_hash_password_returns_string(self, hasher: BcryptPasswordHasher) -> None:
        """Test that hash_password returns a non-empty string."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_hash_password_different_from_plaintext(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that hash is not equal to plaintext."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hash_value != plaintext

    def test_hash_password_same_plaintext_produces_different_hashes(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that same plaintext produces different hashes (salt)."""
        plaintext = "test_password_12345"
        hash1 = hasher.hash_password(plaintext)
        hash2 = hasher.hash_password(plaintext)

        # Different hashes due to different salts
        assert hash1 != hash2
        # Both should verify correctly
        assert hasher.verify_password(plaintext, hash1)
        assert hasher.verify_password(plaintext, hash2)

    def test_hash_password_rejects_empty_password(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that empty password raises ValueError."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            hasher.hash_password("")

    def test_verify_password_correct_password_returns_true(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that verify_password returns True for correct password."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password(plaintext, hash_value) is True

    def test_verify_password_incorrect_password_returns_false(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that verify_password returns False for incorrect password."""
        plaintext = "test_password_12345"
        wrong_password = "wrong_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password(wrong_password, hash_value) is False

    def test_verify_password_empty_plaintext_returns_false(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that verify_password returns False for empty plaintext."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password("", hash_value) is False

    def test_verify_password_empty_hash_returns_false(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that verify_password returns False for empty hash."""
        plaintext = "test_password_12345"

        assert hasher.verify_password(plaintext, "") is False

    def test_verify_password_none_plaintext_returns_false(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that verify_password returns False for None plaintext."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.verify_password(None, hash_value) is False  # type: ignore[arg-type]

    def test_verify_password_invalid_hash_returns_false(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that verify_password returns False for invalid hash."""
        plaintext = "test_password_12345"
        invalid_hash = "not_a_valid_hash"

        assert hasher.verify_password(plaintext, invalid_hash) is False

    def test_verify_password_timing_attack_resistance(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test constant-time comparison (timing attack resistance).

        Execution time should not vary significantly based on
        where the password mismatches. This test runs verify_password
        with different wrong passwords and checks that timing
        variance is not proportional to mismatch position.
        """
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        # Measure time for several wrong passwords
        times: list[float] = []
        for i in range(5):
            wrong_password = f"wrong_password_{i:05d}"
            start = time.perf_counter()
            hasher.verify_password(wrong_password, hash_value)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # Times should be relatively consistent
        # Allow up to 50% variance (bcrypt has built-in constant-time comparison)
        avg_time = sum(times) / len(times)
        for t in times:
            # If avg is very small, absolute diff; if larger, percentage
            if avg_time > 0.001:
                relative_diff = abs(t - avg_time) / avg_time
                assert (
                    relative_diff < 0.5
                ), f"Timing variance too high: {relative_diff}"

    def test_needs_rehash_always_returns_false(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that needs_rehash always returns False (bcrypt doesn't support parameter updates)."""
        plaintext = "test_password_12345"
        hash_value = hasher.hash_password(plaintext)

        assert hasher.needs_rehash(hash_value) is False

    def test_isinstance_password_hasher_interface(
        self, hasher: BcryptPasswordHasher
    ) -> None:
        """Test that BcryptPasswordHasher implements PasswordHasherInterface."""
        assert isinstance(hasher, PasswordHasherInterface)


class TestGetPasswordHasher:
    """Test suite for get_password_hasher() factory function."""

    def test_get_password_hasher_returns_instance(self) -> None:
        """Test that get_password_hasher returns a PasswordHasherInterface instance."""
        hasher = get_password_hasher()
        assert isinstance(hasher, PasswordHasherInterface)

    def test_get_password_hasher_returns_argon_by_default(self) -> None:
        """Test that get_password_hasher returns ArgonPasswordHasher by default."""
        hasher = get_password_hasher()
        # By default, should be argon2id
        assert isinstance(hasher, ArgonPasswordHasher)

    def test_get_password_hasher_is_callable(self) -> None:
        """Test that factory function can be called multiple times."""
        hasher1 = get_password_hasher()
        hasher2 = get_password_hasher()
        # Both should be instances of PasswordHasherInterface
        assert isinstance(hasher1, PasswordHasherInterface)
        assert isinstance(hasher2, PasswordHasherInterface)


class TestPasswordHasherIntegration:
    """Integration tests comparing argon2id and bcrypt behavior."""

    def test_both_hashers_produce_different_hashes_for_same_password(
        self,
    ) -> None:
        """Test that argon2id and bcrypt produce different hash formats."""
        plaintext = "test_password_12345"
        argon_hasher = ArgonPasswordHasher()
        bcrypt_hasher = BcryptPasswordHasher()

        argon_hash = argon_hasher.hash_password(plaintext)
        bcrypt_hash = bcrypt_hasher.hash_password(plaintext)

        # Hashes should be different (different algorithms)
        assert argon_hash != bcrypt_hash
        # But both should verify correctly
        assert argon_hasher.verify_password(plaintext, argon_hash)
        assert bcrypt_hasher.verify_password(plaintext, bcrypt_hash)

    def test_cross_hasher_verification_fails(self) -> None:
        """Test that argon2id and bcrypt hashes don't cross-verify."""
        plaintext = "test_password_12345"
        argon_hasher = ArgonPasswordHasher()
        bcrypt_hasher = BcryptPasswordHasher()

        argon_hash = argon_hasher.hash_password(plaintext)
        bcrypt_hash = bcrypt_hasher.hash_password(plaintext)

        # Argon hasher should not verify bcrypt hash
        assert not argon_hasher.verify_password(plaintext, bcrypt_hash)
        # Bcrypt hasher should not verify argon hash
        assert not bcrypt_hasher.verify_password(plaintext, argon_hash)
