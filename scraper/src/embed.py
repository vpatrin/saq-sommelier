import hashlib
from typing import Any


def build_embedding_text(
    *,
    category: str | None = None,
    taste_tag: str | None = None,
    tasting_profile: dict[str, Any] | None = None,
    grape_blend: list[dict[str, Any]] | None = None,
    grape: str | None = None,
    producer: str | None = None,
    region: str | None = None,
    appellation: str | None = None,
    designation: str | None = None,
    classification: str | None = None,
    country: str | None = None,
    vintage: str | None = None,
    description: str | None = None,
) -> str:
    """Build the composite text that gets embedded for semantic search.

    Format:
        {category} | {taste_tag} | {corps}, {sucre}, {acidite}
        {producer} | {grape} | {region}, {appellation}, ... | {vintage}
        Arômes: {arome}
        {description}

    Missing fields are omitted, not replaced with placeholders.
    Returns empty string if no fields have content.
    """
    lines: list[str] = []

    # Line 1: category + taste profile summary
    line1_parts: list[str] = []
    if category:
        line1_parts.append(category)
    if taste_tag:
        line1_parts.append(taste_tag)
    if tasting_profile:
        body_parts = []
        for key in ("corps", "sucre", "acidite"):
            val = tasting_profile.get(key)
            if val:
                body_parts.append(val)
        if body_parts:
            line1_parts.append(", ".join(body_parts))
    if line1_parts:
        lines.append(" | ".join(line1_parts))

    # Line 2: producer + grape + origin + vintage
    line2_parts: list[str] = []
    if producer:
        line2_parts.append(producer)
    grape_text = _format_grape_blend(grape_blend) if grape_blend else grape
    if grape_text:
        line2_parts.append(grape_text)
    origin_parts = [v for v in (region, appellation, designation, classification, country) if v]
    if origin_parts:
        line2_parts.append(", ".join(origin_parts))
    if vintage:
        line2_parts.append(vintage)
    if line2_parts:
        lines.append(" | ".join(line2_parts))

    # Line 3: aromas (from tasting_profile)
    if tasting_profile:
        arome = tasting_profile.get("arome")
        if arome:
            arome_text = ", ".join(arome) if isinstance(arome, list) else arome
            lines.append(f"Arômes: {arome_text}")

    # Line 4: description (marketing text — semantic richness for occasion matching)
    if description:
        lines.append(description)

    return "\n".join(lines)


def _format_grape_blend(blend: list[dict[str, Any]]) -> str:
    """Format structured grape blend as readable text.

    Input: [{"code": "MALB", "pct": 96}, {"code": "SYRA", "pct": 4}]
    Output: "MALB 96%, SYRA 4%"
    """
    parts = []
    for entry in blend:
        code = entry.get("code", "")
        pct = entry.get("pct", 0)
        if code:
            parts.append(f"{code} {pct}%")
    return ", ".join(parts)


# Fields that contribute to the embedding — if any change, re-embed.
_HASH_FIELDS = (
    "taste_tag",
    "grape_blend",
    "grape",
    "producer",
    "region",
    "appellation",
    "country",
    "category",
    "designation",
    "classification",
    "description",
)


def compute_embedding_input_hash(attrs: dict[str, Any]) -> str:
    """Compute SHA256 of all embedding-relevant fields.

    Returns hex digest. Used for change detection: re-embed when
    embedding_input_hash != last_embedded_hash.
    """
    parts: list[str] = []
    for field in _HASH_FIELDS:
        val = attrs.get(field)
        if val is not None:
            parts.append(f"{field}={val}")

    # tasting_profile sub-fields that affect embedding text
    profile = attrs.get("tasting_profile")
    if profile and isinstance(profile, dict):
        for key in ("corps", "sucre", "acidite", "arome"):
            val = profile.get(key)
            if val is not None:
                parts.append(f"profile.{key}={val}")

    return hashlib.sha256("|".join(parts).encode()).hexdigest()
