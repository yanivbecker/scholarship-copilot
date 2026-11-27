# Background job (launchd)

The daily job (`scholar daily --scheduled`) runs from a macOS launchd agent.
The agent file is **generated**, not copied from here, because launchd needs
absolute paths for this Mac (`uv`, the `api/` folder, the data folder). The
code is in `api/app/modules/background/launchd.py`.

## Switching it on and off (FR-N2)

From `api/`:

```bash
uv run scholar background status   # what's installed, loaded and switched on
uv run scholar background on       # write ~/Library/LaunchAgents/com.scholarshipcopilot.daily.plist and load it
uv run scholar background off      # unload it and delete the file
```

The Settings page in the app calls the same code. "Run now" in the app (and
`uv run scholar daily`) always works, even when background running is off.

## What the agent does

| Setting | Value | Why |
|---|---|---|
| `StartCalendarInterval` | every day at 07:00 | FR-N1. If the Mac was asleep at 07:00, launchd runs it once on wake. If it was shut down, it waits for the next day. |
| `ProgramArguments` | `uv run --directory <api> scholar daily --scheduled` | `--scheduled` makes the job do nothing while background running is switched off. |
| `WorkingDirectory` | `api/` | So the job reads `api/.env` (API keys) like the app does. **No secrets are written into the plist.** |
| `EnvironmentVariables` | `SCHOLARSHIP_DATA_DIR` only | So the job always uses the same data folder as the app. |
| `ProcessType`, `Nice`, `LowPriorityIO` | Background, 10, true | NFR-7: it never competes with what you're doing. |
| `StandardOutPath` / `StandardErrorPath` | `<data folder>/logs/daily.log` | Logs stay with your data, never in the repo. |

## Trying it safely

Set `SCHOLARSHIP_BACKGROUND_DRY_RUN=true`: `on`/`off` then write the plist
into `<data folder>/launchd-dry-run/` and never call `launchctl`. Tests always
run in this mode.
