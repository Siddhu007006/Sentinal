"""Unit tests for the reconciled DigitalAsset domain entity.

Validates the E5.T2 acceptance criteria: immutability, required
SHA-256/MIME/size for the file factory, hash-based identity, and
invalid-hash rejection.

Traces to: 22-Engineering-Backlog E5.T2 (Digital Asset Domain Entity)
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.entities.digital_asset import DigitalAsset


_VALID_HASH = "a3f5c1d8e9f2b7c4a6d1e8f3b7c9d2e1" * 2  # 64 lowercase hex
_OTHER_HASH = "b" * 64


class TestCreateFileFactory:
    def test_create_file_with_required_inputs(self) -> None:
        """E5.T2: sha256_hash, mime_type, size_bytes are required inputs."""
        asset = DigitalAsset.create_file(
            user_id=uuid4(),
            sha256_hash=_VALID_HASH,
            mime_type="application/pdf",
            size_bytes=1024,
            raw_value="report.pdf",
            id=uuid4(),
            upload_id=uuid4(),
        )

        assert asset.asset_type == "file"
        assert asset.sha256_hash == _VALID_HASH
        assert asset.normalized_value == _VALID_HASH
        assert asset.mime_type == "application/pdf"
        assert asset.size_bytes == 1024
        assert asset.storage_key is None  # assigned later in lifecycle

    def test_rejects_invalid_hash_format(self) -> None:
        """E5.T2: invalid hash format rejected."""
        for bad in ["XYZ" * 16, "g" * 64, "a" * 63, "a" * 65, ""]:
            with pytest.raises(ValueError, match="sha256_hash"):
                DigitalAsset.create_file(
                    user_id=uuid4(),
                    sha256_hash=bad,
                    mime_type="application/pdf",
                    size_bytes=1,
                    raw_value="x.pdf",
                    id=uuid4(),
                    upload_id=uuid4(),
                )

    def test_rejects_missing_mime_or_size(self) -> None:
        """file assets require mime_type and size_bytes."""
        with pytest.raises(ValueError, match="mime_type"):
            DigitalAsset(
                id=uuid4(),
                user_id=uuid4(),
                asset_type="file",
                normalized_value=_VALID_HASH,
                raw_value="x.pdf",
                sha256_hash=_VALID_HASH,
                size_bytes=1,
                upload_id=uuid4(),
            )
        with pytest.raises(ValueError, match="size_bytes"):
            DigitalAsset(
                id=uuid4(),
                user_id=uuid4(),
                asset_type="file",
                normalized_value=_VALID_HASH,
                raw_value="x.pdf",
                sha256_hash=_VALID_HASH,
                mime_type="application/pdf",
                upload_id=uuid4(),
            )


class TestCreateIocFactory:
    def test_create_ioc(self) -> None:
        asset = DigitalAsset.create_ioc(
            user_id=uuid4(),
            asset_type="domain",
            raw_value="Evil.Com",
            normalized_value="evil.com",
            id=uuid4(),
        )

        assert asset.asset_type == "domain"
        assert asset.sha256_hash is None  # IOC assets are not content-addressed

    def test_rejects_invalid_asset_type(self) -> None:
        with pytest.raises(ValueError, match="asset_type"):
            DigitalAsset.create_ioc(
                user_id=uuid4(),
                asset_type="certificate",
                raw_value="x",
                normalized_value="x",
                id=uuid4(),
            )


class TestImmutability:
    def test_entity_is_frozen(self) -> None:
        """E5.T2: no field is modifiable after creation."""
        asset = DigitalAsset.create_ioc(
            user_id=uuid4(),
            asset_type="domain",
            raw_value="evil.com",
            normalized_value="evil.com",
            id=uuid4(),
        )

        with pytest.raises(Exception):  # noqa: B017,PT011  # FrozenInstanceError
            asset.raw_value = "changed.com"  # type: ignore[misc]


class TestIdentity:
    def test_hash_equality_is_identity(self) -> None:
        """E5.T2: two assets with the same hash are the same entity."""
        a = DigitalAsset.create_file(
            user_id=uuid4(),
            sha256_hash=_VALID_HASH,
            mime_type="application/pdf",
            size_bytes=1,
            raw_value="a.pdf",
            id=uuid4(),
            upload_id=uuid4(),
        )
        b = DigitalAsset.create_file(
            user_id=uuid4(),  # different originating user
            sha256_hash=_VALID_HASH,
            mime_type="application/pdf",
            size_bytes=1,
            raw_value="b.pdf",
            id=uuid4(),
            upload_id=uuid4(),
        )

        assert a == b  # same content hash → same entity, globally
        assert hash(a) == hash(b)

    def test_different_hash_is_different_entity(self) -> None:
        a = DigitalAsset.create_file(
            user_id=uuid4(),
            sha256_hash=_VALID_HASH,
            mime_type="application/pdf",
            size_bytes=1,
            raw_value="a.pdf",
            id=uuid4(),
            upload_id=uuid4(),
        )
        b = DigitalAsset.create_file(
            user_id=uuid4(),
            sha256_hash=_OTHER_HASH,
            mime_type="application/pdf",
            size_bytes=1,
            raw_value="a.pdf",
            id=uuid4(),
            upload_id=uuid4(),
        )

        assert a != b

    def test_ioc_identity_is_per_user(self) -> None:
        user_a, user_b = uuid4(), uuid4()
        a = DigitalAsset.create_ioc(
            user_id=user_a,
            asset_type="domain",
            raw_value="evil.com",
            normalized_value="evil.com",
            id=uuid4(),
        )
        same_user_same_value = DigitalAsset.create_ioc(
            user_id=user_a,
            asset_type="domain",
            raw_value="evil.com",
            normalized_value="evil.com",
            id=uuid4(),
        )
        other_user_same_value = DigitalAsset.create_ioc(
            user_id=user_b,
            asset_type="domain",
            raw_value="evil.com",
            normalized_value="evil.com",
            id=uuid4(),
        )

        assert a == same_user_same_value
        assert a != other_user_same_value


class TestStructuralInvariants:
    def test_file_hash_type_requires_hash(self) -> None:
        with pytest.raises(ValueError, match="sha256_hash"):
            DigitalAsset(
                id=uuid4(),
                user_id=uuid4(),
                asset_type="file_hash",
                normalized_value="literally-anything",
                raw_value="literally-anything",
            )

    def test_file_type_requires_upload(self) -> None:
        with pytest.raises(ValueError, match="upload_id"):
            DigitalAsset(
                id=uuid4(),
                user_id=uuid4(),
                asset_type="file",
                normalized_value=_VALID_HASH,
                raw_value="x.pdf",
                sha256_hash=_VALID_HASH,
                mime_type="application/pdf",
                size_bytes=1,
                # upload_id intentionally omitted
            )

    def test_negative_size_rejected(self) -> None:
        with pytest.raises(ValueError, match="size_bytes"):
            DigitalAsset(
                id=uuid4(),
                user_id=uuid4(),
                asset_type="file",
                normalized_value=_VALID_HASH,
                raw_value="x.pdf",
                sha256_hash=_VALID_HASH,
                mime_type="application/pdf",
                size_bytes=-1,
                upload_id=uuid4(),
            )
