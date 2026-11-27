"""Application status and which changes are allowed (FR-UI4, FR-A7).

The status path is fixed. Moving forward goes one step at a time; moving
back one step is allowed to undo a mistake. Some steps have conditions the
system checks itself (see service.py), so a click alone can't, for example,
mark a scholarship "eligibility confirmed" when the verdict says otherwise.
"""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    """Where the student is with one scholarship."""

    DISCOVERED = "discovered"
    ELIGIBILITY_CONFIRMED = "eligibility_confirmed"
    READY_TO_APPLY = "ready_to_apply"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    SUBMITTED = "submitted"
    WON = "won"
    REJECTED = "rejected"


S = ApplicationStatus

LABELS: dict[ApplicationStatus, str] = {
    S.DISCOVERED: "Discovered",
    S.ELIGIBILITY_CONFIRMED: "Eligibility confirmed",
    S.READY_TO_APPLY: "Ready to apply",
    S.IN_PROGRESS: "In progress",
    S.AWAITING_APPROVAL: "Awaiting approval",
    S.SUBMITTED: "Submitted",
    S.WON: "Won",
    S.REJECTED: "Rejected",
}

# Every allowed change. Anything not listed is refused.
TRANSITIONS: dict[ApplicationStatus, tuple[ApplicationStatus, ...]] = {
    S.DISCOVERED: (S.ELIGIBILITY_CONFIRMED,),
    S.ELIGIBILITY_CONFIRMED: (S.READY_TO_APPLY, S.DISCOVERED),
    S.READY_TO_APPLY: (S.IN_PROGRESS, S.ELIGIBILITY_CONFIRMED),
    S.IN_PROGRESS: (S.AWAITING_APPROVAL, S.READY_TO_APPLY),
    S.AWAITING_APPROVAL: (S.SUBMITTED, S.IN_PROGRESS),
    # Undoing "submitted" is allowed for mistakes, and is audited like any change.
    S.SUBMITTED: (S.WON, S.REJECTED, S.AWAITING_APPROVAL),
    S.WON: (S.SUBMITTED,),
    S.REJECTED: (S.SUBMITTED,),
}

ORDER = tuple(ApplicationStatus)


def is_forward(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return ORDER.index(target) > ORDER.index(current)
