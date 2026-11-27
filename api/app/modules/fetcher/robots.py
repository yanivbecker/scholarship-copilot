"""robots.txt rules, fetched once per site per run (CLAUDE.md, FR-D2)."""

from dataclasses import dataclass
from urllib.robotparser import RobotFileParser

# The name sites can use in robots.txt to give us specific rules.
ROBOTS_AGENT = "ScholarshipCopilot"


@dataclass(frozen=True)
class RobotsRules:
    """What one site's robots.txt allows for us."""

    parser: RobotFileParser | None  # None = no usable file
    allow_all: bool
    # Set when robots.txt couldn't be read, so we don't know the rules.
    unavailable_reason: str | None = None

    def allows(self, url: str) -> bool:
        if self.parser is None:
            return self.allow_all
        return self.parser.can_fetch(ROBOTS_AGENT, url)

    def crawl_delay(self) -> float | None:
        if self.parser is None:
            return None
        delay = self.parser.crawl_delay(ROBOTS_AGENT)
        return float(delay) if delay is not None else None


def rules_from_response(
    status: int | None, body: str, error: str | None = None
) -> RobotsRules:
    """Turn the robots.txt response into rules, erring on the side of caution.

    * 200: follow the file.
    * 404 / 410 (and other 4xx except 401/403/429): there are no rules.
    * 401 / 403: the site restricts access; treat everything as disallowed.
    * 429 / 5xx / network failure (status None): unknown, so don't fetch now.
    """
    if status == 200:
        parser = RobotFileParser()
        parser.parse(body.splitlines())
        return RobotsRules(parser, allow_all=False)
    if status is not None and 400 <= status < 500 and status not in (401, 403, 429):
        return RobotsRules(None, allow_all=True)
    if status is None:
        reason = error or "the site couldn't be reached"
    elif status in (401, 403):
        reason = f"the site restricts its robots.txt ({status})"
    else:
        reason = f"the site's robots.txt answered with error {status}"
    return RobotsRules(None, allow_all=False, unavailable_reason=reason)
