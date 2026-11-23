import re

from .models import CreatorProfile
from .views import public_creator_fields


_CREATOR_TERMS = re.compile(
    r"\b(founder|creator|created|developed|project owner|behind satell|professional background)\b|"
    r"\b(founder'?s|creator'?s)\s+(linkedin|github|leetcode|hackerrank|portfolio|profile)\b",
    re.IGNORECASE,
)


def is_creator_question(question: str) -> bool:
    text = " ".join(question.split())
    if not _CREATOR_TERMS.search(text):
        return False
    lowered = text.casefold()
    return ("satell" in lowered or "project owner" in lowered
            or "founder" in lowered or "creator" in lowered)


def answer_creator_question(question: str) -> str | None:
    if not is_creator_question(question):
        return None
    profile = CreatorProfile.objects.filter(key="satell").first()
    public = public_creator_fields(profile)
    if public is None:
        return "I don't have publicly enabled, verified creator-profile details to share right now."

    parts = []
    if public["name"]:
        parts.append(f"{public['name']} is listed in Satell's trusted creator profile as its creator and project owner.")
    else:
        parts.append("Satell's creator profile is configured, but the creator's name is not enabled for public display.")
    if public["headline"]:
        parts.append(public["headline"])
    if public["current_role"]:
        parts.append(f"Current role: {public['current_role']}.")
    if public["biography"]:
        parts.append(public["biography"])
    for label, key in (("Education", "education"), ("Experience", "experience"),
                       ("Skills and technical interests", "skills"), ("Projects", "projects")):
        if public[key]:
            parts.append(f"{label}: {public[key]}")
    if public["links"]:
        parts.append("Public professional profiles: " + ", ".join(
            f"[{item['label']}]({item['url']})" for item in public["links"]
        ) + ".")
    if (public["owner_supplied_details_public"]
            and public["verification_status"] == "Supplied by owner; not independently verified"):
        parts.append("Profile background details were supplied by the owner and have not been independently verified.")
    lowered = question.casefold()
    if "background" in lowered and not any(public[key] for key in ("headline", "biography", "current_role", "experience", "education")):
        parts.append("Professional background details are not currently enabled for public display.")
    if "project" in lowered and ("other" in lowered or "developed" in lowered):
        if not public["projects"]:
            parts.append("Project details are not currently enabled for public display.")
    return "\n\n".join(parts)
