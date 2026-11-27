"""Run the API server: `uv run python -m app` (from the api/ folder)."""

import uvicorn

from app.core.config import get_settings

# NFR-3: the API listens on the loopback interface only.
# Deliberately not configurable, so it can't be exposed to the network by accident.
HOST = "127.0.0.1"


def main() -> None:
    uvicorn.run("app.main:app", host=HOST, port=get_settings().port)


if __name__ == "__main__":
    main()
