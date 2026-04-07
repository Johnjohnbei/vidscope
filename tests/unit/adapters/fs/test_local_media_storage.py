"""Tests for :class:`LocalMediaStorage`."""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.adapters.fs.local_media_storage import LocalMediaStorage
from vidscope.domain.errors import StorageError
from vidscope.ports import MediaStorage


@pytest.fixture()
def storage(tmp_path: Path) -> LocalMediaStorage:
    return LocalMediaStorage(tmp_path)


@pytest.fixture()
def source_file(tmp_path: Path) -> Path:
    src = tmp_path / "source.bin"
    src.write_bytes(b"hello world" * 100)
    return src


class TestConstructor:
    def test_absolute_root_is_accepted(self, tmp_path: Path) -> None:
        storage = LocalMediaStorage(tmp_path)
        assert storage.resolve("videos/1/media.mp4").is_absolute()

    def test_relative_root_is_rejected(self) -> None:
        with pytest.raises(StorageError):
            LocalMediaStorage(Path("relative/path"))

    def test_missing_root_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(StorageError):
            LocalMediaStorage(tmp_path / "does-not-exist")


class TestStoreAndRetrieve:
    def test_round_trip(
        self, storage: LocalMediaStorage, source_file: Path
    ) -> None:
        key = "videos/1/media.mp4"
        stored_key = storage.store(key, source_file)
        assert stored_key == key

        assert storage.exists(key)
        resolved = storage.resolve(key)
        assert resolved.exists()
        assert resolved.read_bytes() == source_file.read_bytes()

    def test_normalizes_backslash_to_forward_slash(
        self, storage: LocalMediaStorage, source_file: Path
    ) -> None:
        stored_key = storage.store("videos\\2\\frames\\0.jpg", source_file)
        assert stored_key == "videos/2/frames/0.jpg"
        assert storage.exists("videos/2/frames/0.jpg")

    def test_store_overwrites_existing_atomically(
        self, storage: LocalMediaStorage, tmp_path: Path
    ) -> None:
        src1 = tmp_path / "v1.bin"
        src1.write_bytes(b"first")
        src2 = tmp_path / "v2.bin"
        src2.write_bytes(b"second content")

        storage.store("videos/3/media.mp4", src1)
        assert storage.resolve("videos/3/media.mp4").read_bytes() == b"first"

        storage.store("videos/3/media.mp4", src2)
        assert (
            storage.resolve("videos/3/media.mp4").read_bytes()
            == b"second content"
        )

    def test_store_missing_source_raises(
        self, storage: LocalMediaStorage, tmp_path: Path
    ) -> None:
        with pytest.raises(StorageError):
            storage.store("videos/x/media.mp4", tmp_path / "nope.bin")

    def test_store_creates_parent_directories(
        self, storage: LocalMediaStorage, source_file: Path
    ) -> None:
        storage.store("deep/nested/path/file.bin", source_file)
        assert storage.exists("deep/nested/path/file.bin")

    def test_store_leaves_no_tmp_sidecar(
        self, storage: LocalMediaStorage, source_file: Path, tmp_path: Path
    ) -> None:
        storage.store("videos/10/media.mp4", source_file)
        # No *.tmp files left under the root after a successful store.
        leftovers = list(tmp_path.rglob("*.tmp"))
        assert leftovers == []


class TestDelete:
    def test_delete_existing(
        self, storage: LocalMediaStorage, source_file: Path
    ) -> None:
        storage.store("videos/5/media.mp4", source_file)
        assert storage.exists("videos/5/media.mp4")
        storage.delete("videos/5/media.mp4")
        assert not storage.exists("videos/5/media.mp4")

    def test_delete_missing_is_noop(self, storage: LocalMediaStorage) -> None:
        # Must not raise
        storage.delete("videos/never/existed.mp4")

    def test_delete_invalid_key_is_noop(
        self, storage: LocalMediaStorage
    ) -> None:
        # Invalid keys don't exist; delete should not raise
        storage.delete("../etc/passwd")


class TestOpen:
    def test_open_returns_readable_handle(
        self, storage: LocalMediaStorage, source_file: Path
    ) -> None:
        storage.store("videos/6/media.mp4", source_file)
        with storage.open("videos/6/media.mp4") as fh:
            data = fh.read()
        assert data == source_file.read_bytes()

    def test_open_missing_raises(self, storage: LocalMediaStorage) -> None:
        with pytest.raises(StorageError):
            storage.open("videos/nope/media.mp4")


class TestSecurityConstraints:
    def test_absolute_key_is_rejected(self, storage: LocalMediaStorage) -> None:
        with pytest.raises(StorageError):
            storage.resolve("/etc/passwd")

    def test_windows_absolute_key_is_rejected(
        self, storage: LocalMediaStorage
    ) -> None:
        with pytest.raises(StorageError):
            storage.resolve("\\windows\\system32\\cmd.exe")

    def test_traversal_key_is_rejected(
        self, storage: LocalMediaStorage
    ) -> None:
        with pytest.raises(StorageError):
            storage.resolve("../../secret.txt")

    def test_empty_key_is_rejected(self, storage: LocalMediaStorage) -> None:
        with pytest.raises(StorageError):
            storage.resolve("")

    def test_exists_returns_false_for_invalid_keys(
        self, storage: LocalMediaStorage
    ) -> None:
        assert storage.exists("../escape") is False


class TestProtocolConformance:
    def test_conforms_to_media_storage_protocol(
        self, storage: LocalMediaStorage
    ) -> None:
        assert isinstance(storage, MediaStorage)
