"""Print the API's OpenAPI schema as JSON (used to generate frontend types).

Run from api/: `uv run python -m app.export_openapi > ../web/src/api/openapi.json`
No server, database, or data directory is needed.
"""

import json

from app.main import create_app


def main() -> None:
    print(json.dumps(create_app().openapi(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
