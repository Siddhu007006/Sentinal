"""Password hashing service with adaptive algorithm support.

Provides secure password hashing and verification using either argon2id (default)
or bcrypt, with constant-time comparison to prevent timing attacks.

Per design.md § Password Hashing Service and Requirement 2 in requirements.md:
- Hash is non-reversible
- Same plaintext produces different hashes (salt)
- verify_password() uses constant-time comparison
- Never logs passwords/hashes
- Work factor ~100ms on modern CPU

Traces to: 08-Security-Architecture §4 (password hashing, timing attack prevention)
Traces to: 07-Backend-Development-Standards §11 (algorithm selection)
"""

from abc import ABC, abstractmethod


class PasswordHasherInterface(ABC):
    """Abstract interface for password hashing implementations.

    All implementations MUST use constant-time verification to prevent timing attacks.
    """

    @abstractmethod
    def hash_password(self, plaintext: str) -> str:
        """Hash plaintext password with salt.

        Args:
            plaintext: The plaintext password to hash.

        Returns:
            Non-reversible hash string with salt included.

        Raises:
            ValueError: If plaintext is empty.
        """
        pass

    @abstractmethod
    def verify_password(self, plaintext: str, hash_value: str) -> bool:
        """Verify plaintext against hash using constant-time comparison.

        Args:
            plaintext: The plaintext password to verify.
            hash_value: The hash to verify against.

        Returns:
            True if plaintext matches hash, False otherwise.

        Note:
            Execution time MUST NOT vary based on mismatch position
            (timing-attack resistant).
        """
        pass

    @abstractmethod
    def needs_rehash(self, hash_value: str) -> bool:
        """Check if hash needs recomputation due to parameter changes.

        Args:
            hash_value: The hash to check.

        Returns:
            True if rehashing is recommended, False otherwise.
        """
        pass


class ArgonPasswordHasher(PasswordHasherInterface):
    """Password hashing using argon2id.

    Per 07-Backend-Development-Standards.md §11:
    - Work factor tuned for ~100ms computation on modern CPU
    - Uses argon2id (resistant to both GPU and side-channel attacks)
    - Salt is automatically generated and included in hash

    Configuration:
    - time_cost=2: iterations
    - memory_cost=65536: 64MB memory
    - parallelism=4: 4 threads
    - hash_len=16: output length
    - salt_len=16: salt length
    """

    def __init__(self) -> None:
        """Initialize argon2id hasher with production-grade parameters."""
        from argon2 import PasswordHasher as Argon2PasswordHasher

        # Configure argon2id with work factor ~100ms
        self.hasher = Argon2PasswordHasher(
            time_cost=2,  # iterations
            memory_cost=65536,  # 64MB memory
            parallelism=4,  # 4 threads
            hash_len=16,
            salt_len=16,
        )

    def hash_password(self, plaintext: str) -> str:
        """Hash password using argon2id.

        Preconditions:
        - plaintext is non-empty string

        Postconditions:
        - Returns hash string (not equal to plaintext)
        - Salt is unique per call
        - Same plaintext produces different hash each time

        Args:
            plaintext: The plaintext password to hash.

        Returns:
            Argon2id hash string with embedded salt.

        Raises:
            ValueError: If password is empty.
        """
        if not plaintext:
            raise ValueError("Password cannot be empty")

        return self.hasher.hash(plaintext)

    def verify_password(self, plaintext: str, hash_value: str) -> bool:
        """Verify plaintext against hash using constant-time comparison.

        The argon2 library uses constant-time comparison internally,
        preventing timing attacks.

        Preconditions:
        - plaintext is non-empty string
        - hash_value is valid argon2id hash

        Postconditions:
        - Returns True if match, False if mismatch
        - Execution time does NOT vary based on mismatch position

        Args:
            plaintext: The plaintext password to verify.
            hash_value: The argon2id hash to verify against.

        Returns:
            True if password is correct, False otherwise.
        """
        if not plaintext or not hash_value:
            return False

        try:
            from argon2.exceptions import InvalidHashError, VerifyMismatchError

            # Argon2 library uses constant-time comparison internally
            self.hasher.verify(hash_value, plaintext)
            return True
        except (VerifyMismatchError, InvalidHashError, TypeError):
            return False

    def needs_rehash(self, hash_value: str) -> bool:
        """Check if hash needs recomputation due to parameter changes.

        Args:
            hash_value: The argon2id hash to check.

        Returns:
            True if rehashing is recommended, False otherwise.
        """
        return self.hasher.check_needs_rehash(hash_value)


class BcryptPasswordHasher(PasswordHasherInterface):
    """Alternative: bcrypt password hashing.

    Per 08-Security-Architecture.md §4:
    - Industry standard, widely used
    - Simpler than argon2id but still secure
    - Work factor (cost) tuned for ~100ms computation

    Configuration:
    - cost=12: work factor (typically 100ms on modern CPU)
    """

    def __init__(self, cost: int = 12) -> None:
        """Initialize bcrypt hasher with production-grade cost.

        Args:
            cost: Bcrypt cost factor (default 12 for ~100ms computation).
        """
        import bcrypt

        self.bcrypt = bcrypt
        self.cost = cost

    def hash_password(self, plaintext: str) -> str:
        """Hash using bcrypt with configured cost.

        Preconditions:
        - plaintext is non-empty string

        Postconditions:
        - Returns hash string (not equal to plaintext)
        - Salt is unique per call
        - Same plaintext produces different hash each time

        Args:
            plaintext: The plaintext password to hash.

        Returns:
            Bcrypt hash string with embedded salt.

        Raises:
            ValueError: If password is empty.
        """
        if not plaintext:
            raise ValueError("Password cannot be empty")

        salt = self.bcrypt.gensalt(rounds=self.cost)
        return self.bcrypt.hashpw(plaintext.encode(), salt).decode()

    def verify_password(self, plaintext: str, hash_value: str) -> bool:
        """Verify with constant-time comparison.

        The bcrypt library's checkpw() uses constant-time comparison internally,
        preventing timing attacks.

        Preconditions:
        - plaintext is non-empty string
        - hash_value is valid bcrypt hash

        Postconditions:
        - Returns True if match, False if mismatch
        - Execution time does NOT vary based on mismatch position

        Args:
            plaintext: The plaintext password to verify.
            hash_value: The bcrypt hash to verify against.

        Returns:
            True if password is correct, False otherwise.
        """
        if not plaintext or not hash_value:
            return False

        try:
            # bcrypt.checkpw uses constant-time comparison
            return self.bcrypt.checkpw(
                plaintext.encode(), hash_value.encode()
            )
        except (TypeError, ValueError):
            return False

    def needs_rehash(self, hash_value: str) -> bool:
        """Check if hash needs recomputation.

        Bcrypt doesn't support parameter updates, so always return False.

        Args:
            hash_value: The bcrypt hash to check.

        Returns:
            Always False (bcrypt doesn't track parameter changes).
        """
        return False


def get_password_hasher() -> PasswordHasherInterface:
    """Get password hasher instance based on configuration.

    Per 07-Backend-Development-Standards.md §11, algorithm is configured
    via settings. Default to argon2id.

    The hasher is selected from settings.security.password_hashing_algorithm,
    which can be either "argon2id" or "bcrypt".

    Returns:
        PasswordHasherInterface instance (ArgonPasswordHasher or BcryptPasswordHasher).

    Raises:
        ValueError: If configured algorithm is not supported.
    """
    from app.core.dependencies import get_settings

    settings = get_settings()
    algorithm = settings.security.password_hashing_algorithm

    if algorithm == "argon2id":
        return ArgonPasswordHasher()
    elif algorithm == "bcrypt":
        return BcryptPasswordHasher(cost=12)
    else:
        msg = (
            f"Unsupported password hashing algorithm: {algorithm}. "
            "Must be one of: argon2id, bcrypt"
        )
        raise ValueError(msg)
