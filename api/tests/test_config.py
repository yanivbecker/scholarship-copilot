"""Tests for data-directory resolution (NFR-1: personal data stays outside the repo)."""

from pathlib import Path

import pytest

from app.core.config import DEFAULT_DATA_DIR, REPO_ROOT, resolve_data_dir


def test_missing_setting_falls_back_to_default() -> None:
    assert resolve_data_dir(None) == DEFAULT_DATA_DIR.expanduser().resolve()


def test_tilde_is_expanded_to_absolute_path() -> None:
    result = resolve_data_dir(Path("~/SomeData"))

    assert result.is_absolute()
    assert result == Path.home().resolve() / "SomeData"


def test_path_outside_repo_is_accepted(tmp_path: Path) -> None:
    assert resolve_data_dir(tmp_path) == tmp_path.resolve()


@pytest.mark.parametrize(
    "inside",
    [
        REPO_ROOT,  # the repo itself
        REPO_ROOT / "data",  # a subfolder
        REPO_ROOT / "api" / ".." / "data",  # sneaky ".." still lands inside
    ],
)
def test_path_inside_repo_is_rejected(inside: Path) -> None:
    with pytest.raises(ValueError, match="outside the repository"):
        resolve_data_dir(inside)


def test_symlink_into_repo_is_rejected(tmp_path: Path) -> None:
    # A link that lives outside the repo but points into it must still fail.
    link = tmp_path / "looks-safe"
    link.symlink_to(REPO_ROOT)

    with pytest.raises(ValueError, match="outside the repository"):
        resolve_data_dir(link)
