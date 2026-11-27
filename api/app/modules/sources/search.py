"""Weekly search for new scholarship pages (FR-N3, FR-D1).

Owner decision (2026-11-27): the student writes the queries. The app only
*suggests* them, from an allowlist of facts that describe what the student
studies, not who they are. Identifying facts (name, email, phone, school,
city) and sensitive ones (citizenship, finances, demographics) are never used.
Nothing is sent until the student saves queries on the Settings page.
"""

from sqlalchemy.orm import Session

from app.modules.profile import repository as profile_repo
from app.modules.profile.catalog import choice_label

# The only facts a suggested query may contain.
QUERY_FACTS = (
    "education_level",
    "major",
    "intended_career",
    "state_of_residence",
    "expected_graduation_year",
)


def suggest_queries(session: Session, user_id: int) -> list[str]:
    facts = {
        f.key: f.value
        for f in profile_repo.list_facts(session, user_id)
        if f.key in QUERY_FACTS
    }
    level = facts.get("education_level")
    level_text = choice_label(level).lower() if isinstance(level, str) else None
    major = facts.get("major") if isinstance(facts.get("major"), str) else None
    career = facts.get("intended_career")
    state = facts.get("state_of_residence")
    year = facts.get("expected_graduation_year")

    suggestions = []
    if major:
        suggestions.append(f"{major} scholarship" + (f" {state}" if state else ""))
    if level_text:
        suggestions.append(
            f"scholarships for {level_text} students"
            + (f" in {state}" if state else "")
        )
    if isinstance(career, str) and career:
        suggestions.append(f"{career} scholarship")
    if level_text and isinstance(year, int):
        suggestions.append(f"{level_text} scholarship class of {year}")
    if not suggestions:
        suggestions.append("undergraduate scholarship application")
    return list(dict.fromkeys(" ".join(s.split()) for s in suggestions))
