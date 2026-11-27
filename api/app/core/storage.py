"""File storage behind a small interface (NFR-8).

Today files live in the data dir (never the repo, NFR-1). A cloud bucket can
replace LocalFileStorage later without changing any caller.

Stored names are random. The original file name is only kept as a label in
the database, so a hostile name like "../../.bashrc" can't choose where a
file lands.
"""

import secrets
from pathlib import Path
from typing import Protocol

from app.core.config import get_data_dir


class FileStorage(Protocol):
    """What the rest of the app needs from storage."""

    def save(self, data: bytes, *, suffix: str) -> str:
        """Store bytes and return an opaque key for them."""
        ...  # pylint: disable=unnecessary-ellipsis

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalFileStorage:
    """Files in a folder on this computer, readable only by this user."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def save(self, data: bytes, *, suffix: str) -> str:
        if not suffix.startswith(".") or not suffix[1:].isalnum():
            raise ValueError(f"Bad file suffix: {suffix!r}")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        key = secrets.token_hex(16) + suffix
        path = self._path(key)
        path.write_bytes(data)
        path.chmod(0o600)
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _path(self, key: str) -> Path:
        # Keys are flat names we generated; refuse anything else.
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError(f"Bad storage key: {key!r}")
        return path


def get_storage() -> FileStorage:
    """FastAPI dependency. Tests override it with a temporary folder."""
    return LocalFileStorage(get_data_dir() / "files")
