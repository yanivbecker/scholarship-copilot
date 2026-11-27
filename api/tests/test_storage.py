"""Local file storage (NFR-1, NFR-8)."""

import stat
from pathlib import Path

import pytest

from app.core.storage import LocalFileStorage


def test_save_read_delete(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "files")

    key = storage.save(b"hello", suffix=".pdf")

    assert key.endswith(".pdf") and len(key) == 36  # random 32-hex name
    assert storage.read(key) == b"hello"
    storage.delete(key)
    assert not (tmp_path / "files" / key).exists()
    storage.delete(key)  # deleting twice is fine


def test_files_are_private_to_this_user(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "files")
    key = storage.save(b"x", suffix=".docx")

    file_mode = stat.S_IMODE((tmp_path / "files" / key).stat().st_mode)
    dir_mode = stat.S_IMODE((tmp_path / "files").stat().st_mode)
    assert file_mode == 0o600
    assert dir_mode == 0o700


@pytest.mark.parametrize(
    "key", ["../escape.pdf", "/etc/passwd", "sub/dir.pdf", "..", "a/../../b"]
)
def test_keys_cannot_point_outside_the_folder(tmp_path: Path, key: str) -> None:
    storage = LocalFileStorage(tmp_path / "files")

    with pytest.raises(ValueError):
        storage.read(key)
    with pytest.raises(ValueError):
        storage.delete(key)


@pytest.mark.parametrize("suffix", ["pdf", ".p/df", "../.pdf", ""])
def test_bad_suffixes_are_rejected(tmp_path: Path, suffix: str) -> None:
    with pytest.raises(ValueError):
        LocalFileStorage(tmp_path).save(b"x", suffix=suffix)
