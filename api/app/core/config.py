"""Application settings, read from environment variables (and an optional .env).

Every variable uses the SCHOLARSHIP_ prefix, e.g. SCHOLARSHIP_DATA_DIR.
Secrets and personal paths never live in code (NFR-1, NFR-2).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view of the SCHOLARSHIP_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SCHOLARSHIP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Raw value of SCHOLARSHIP_DATA_DIR. None when the variable is not set.
    # Use get_data_dir() rather than reading this directly.
    data_dir: Path | None = None

    # Optional full SQLAlchemy URL, e.g. postgresql+psycopg://... for the cloud
    # later (NFR-8). When unset, a SQLite file inside the data dir is used.
    database_url: str | None = None

    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them (also easy to override in tests)."""
    return Settings()


# api/app/core/config.py -> parents[3] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Used when SCHOLARSHIP_DATA_DIR is not set (the documented default location).
DEFAULT_DATA_DIR = Path("~/ScholarshipCopilotData")


def resolve_data_dir(raw: Path | None, repo_root: Path = REPO_ROOT) -> Path:
    """Turn the configured data directory into a safe, absolute Path.

    This is where personal data (DB, uploaded files, backups) will live, so it
    must never point inside the git repository (NFR-1).

    Pure function: it only computes and checks the path, it never touches the
    disk. Creating the folder is get_data_dir()'s job.
    """
    path = (raw or DEFAULT_DATA_DIR).expanduser().resolve()
    if path.is_relative_to(repo_root.resolve()):
        raise ValueError(
            f"SCHOLARSHIP_DATA_DIR must be outside the repository ({repo_root}), "
            f"got {path}. Personal data must never be stored in the repo (NFR-1)."
        )
    return path


def get_data_dir() -> Path:
    """Return the data directory, creating it (owner-only access) if needed."""
    path = resolve_data_dir(get_settings().data_dir)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


SQLITE_FILENAME = "scholarship.db"


def get_database_url() -> str:
    """SCHOLARSHIP_DATABASE_URL if set, otherwise SQLite in the data dir."""
    settings = get_settings()
    if settings.database_url:
        return settings.database_url
    return f"sqlite:///{get_data_dir() / SQLITE_FILENAME}"
