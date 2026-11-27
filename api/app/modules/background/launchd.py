"""The macOS background job: a launchd agent that runs `scholar daily` (FR-N1, N2).

    scholar background on      install the agent and load it
    scholar background off     unload it and remove its file
    scholar background status  what's installed, loaded and switched on

Design choices (see ARCHITECTURE.md):

* The plist is built with plistlib (always valid XML) with absolute paths,
  because launchd starts jobs with almost no environment.
* No secrets go in the plist. WorkingDirectory is api/, so the job reads API
  keys from api/.env exactly like the app does.
* StartCalendarInterval 07:00: if the Mac was asleep at 07:00, launchd runs
  the job once when it wakes (FR-N1). Background priority (NFR-7).
* "Off" removes the file too: agents left in ~/Library/LaunchAgents are
  loaded again at the next login.
* Every launchctl call goes through `Launchctl`, so tests (and dry runs)
  never touch the real launchd.
"""

import os
import plistlib
import shutil
import subprocess  # nosec B404 - fixed argument lists, no shell
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

LABEL = "com.scholarshipcopilot.daily"
DEFAULT_HOUR = 7
API_DIR = Path(__file__).resolve().parents[3]


class BackgroundError(RuntimeError):
    """Something went wrong switching the job. The message is user-facing."""


class Launchctl(Protocol):
    """The three launchctl operations we need."""

    def bootstrap(self, plist: Path) -> None: ...  # load
    def bootout(self) -> None: ...  # unload (fine if not loaded)
    def is_loaded(self) -> bool: ...


@dataclass
class RealLaunchctl:
    """Runs /bin/launchctl for the current user's GUI session."""

    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run

    @property
    def _domain(self) -> str:
        return f"gui/{os.getuid()}"

    def _call(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run(
            ["/bin/launchctl", *args], capture_output=True, text=True, check=False
        )

    def bootstrap(self, plist: Path) -> None:
        result = self._call("bootstrap", self._domain, str(plist))
        if result.returncode != 0:
            raise BackgroundError(
                "launchctl couldn't load the job: "
                + (result.stderr.strip() or f"exit code {result.returncode}")
            )

    def bootout(self) -> None:
        self._call("bootout", f"{self._domain}/{LABEL}")  # errors if not loaded

    def is_loaded(self) -> bool:
        return self._call("print", f"{self._domain}/{LABEL}").returncode == 0


@dataclass
class DryRunLaunchctl:
    """Records what would happen. Used by tests and SCHOLARSHIP_BACKGROUND_DRY_RUN."""

    calls: list[str] = field(default_factory=list)
    loaded: bool = False

    def bootstrap(self, plist: Path) -> None:
        self.calls.append(f"bootstrap {plist}")
        self.loaded = True

    def bootout(self) -> None:
        self.calls.append("bootout")
        self.loaded = False

    def is_loaded(self) -> bool:
        return self.loaded


def build_plist(
    *, uv: Path, api_dir: Path, data_dir: Path, hour: int = DEFAULT_HOUR
) -> dict[str, Any]:
    logs = data_dir / "logs"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(uv),
            "run",
            "--directory",
            str(api_dir),
            "scholar",
            "daily",
            "--scheduled",
        ],
        "WorkingDirectory": str(api_dir),  # so api/.env (keys) is read
        "EnvironmentVariables": {"SCHOLARSHIP_DATA_DIR": str(data_dir)},
        "StartCalendarInterval": {"Hour": hour, "Minute": 0},
        "RunAtLoad": False,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "StandardOutPath": str(logs / "daily.log"),
        "StandardErrorPath": str(logs / "daily.log"),
    }


@dataclass(frozen=True)
class Agent:
    """Where the agent file lives and how to switch it."""

    agents_dir: Path
    launchctl: Launchctl
    data_dir: Path
    find_uv: Callable[[], str | None] = lambda: shutil.which("uv")

    @property
    def plist_path(self) -> Path:
        return self.agents_dir / f"{LABEL}.plist"

    def install(self) -> Path:
        uv = self.find_uv()
        if not uv:
            raise BackgroundError(
                "Couldn't find `uv` on your PATH, which the job needs to run."
            )
        content = build_plist(
            uv=Path(uv).resolve(), api_dir=API_DIR, data_dir=self.data_dir
        )
        (self.data_dir / "logs").mkdir(mode=0o700, parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.plist_path.with_suffix(".tmp")
        with tmp.open("wb") as handle:
            plistlib.dump(content, handle)
        tmp.replace(self.plist_path)  # atomic: launchd never sees half a file
        if self.launchctl.is_loaded():
            self.launchctl.bootout()  # reload with the new file
        self.launchctl.bootstrap(self.plist_path)
        return self.plist_path

    def remove(self) -> None:
        if self.launchctl.is_loaded():
            self.launchctl.bootout()
        self.plist_path.unlink(missing_ok=True)

    def installed(self) -> bool:
        return self.plist_path.exists()
