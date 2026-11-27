"""Profile settings, the fact catalog, and facts (FR-P3, FR-P4, FR-P6, FR-P7)."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.modules.profile import service
from app.modules.profile.catalog import (
    CATALOG,
    SECTION_LABELS,
    SENSITIVE_SECTIONS,
    choice_label,
)
from app.modules.profile.schemas import (
    CatalogOut,
    ChoiceOut,
    FactDefinitionOut,
    FactIn,
    FactOut,
    MissingFactsOut,
    ProfileOut,
    ProfileUpdate,
    SectionOut,
)

router = APIRouter(tags=["profile"])


@router.get("/profile")
def get_profile(session: SessionDep, user: CurrentUser) -> ProfileOut:
    profile = service.get_or_create_profile(session, user.id)
    session.commit()
    return ProfileOut(
        display_name=user.display_name,
        operating_mode=profile.operating_mode,
        onboarding_step=profile.onboarding_step,
        onboarding_completed_at=profile.onboarding_completed_at,
    )


@router.patch("/profile")
def update_profile(
    body: ProfileUpdate, session: SessionDep, user: CurrentUser
) -> ProfileOut:
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or user.display_name
    if body.operating_mode is not None:
        service.set_operating_mode(session, user.id, body.operating_mode)
    session.commit()
    return get_profile(session, user)


@router.get("/facts/catalog")
def get_fact_catalog() -> CatalogOut:
    sections = [
        SectionOut(
            key=section,
            label=label,
            sensitive=section in SENSITIVE_SECTIONS,
            facts=[
                FactDefinitionOut(
                    key=d.key,
                    label=d.label,
                    type=d.type,
                    section=d.section,
                    sensitive=d.sensitive,
                    help=d.help,
                    choices=[
                        ChoiceOut(value=c, label=choice_label(c)) for c in d.choices
                    ],
                    min_value=d.min_value,
                    max_value=d.max_value,
                )
                for d in CATALOG.values()
                if d.section is section
            ],
        )
        for section, label in SECTION_LABELS.items()
    ]
    return CatalogOut(sections=sections)


@router.get("/facts")
def list_facts(session: SessionDep, user: CurrentUser) -> list[FactOut]:
    return [FactOut.model_validate(f) for f in service.list_facts(session, user.id)]


@router.get("/facts/missing")
def get_missing_facts(
    session: SessionDep,
    user: CurrentUser,
    keys: Annotated[list[str], Query(max_length=100)],
) -> MissingFactsOut:
    return MissingFactsOut(missing=service.missing_fact_keys(session, user.id, keys))


@router.put("/facts/{key}")
def set_fact(key: str, body: FactIn, session: SessionDep, user: CurrentUser) -> FactOut:
    fact = service.set_fact(session, user.id, key, body.value, origin=body.origin)
    session.commit()
    return FactOut.model_validate(fact)


@router.delete("/facts/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fact(key: str, session: SessionDep, user: CurrentUser) -> Response:
    service.delete_fact(session, user.id, key)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
