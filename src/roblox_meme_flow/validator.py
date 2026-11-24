from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from roblox_meme_flow.models import EpisodeSpec

HANDLE_RE = re.compile(r"^@[A-Z][A-Za-z0-9]*$")
HANDLE_MENTION_RE = re.compile(r"@[A-Za-z0-9_]+")
EM_DASH = "\u2014"


@dataclass(frozen=True)
class ValidationIssue:
    severity: Literal["error", "warning"]
    code: str
    message: str


def _check_em_dash(issues: list[ValidationIssue], field_name: str, text: str) -> None:
    if EM_DASH in text:
        issues.append(
            ValidationIssue(
                severity="error",
                code="NO_EM_DASH",
                message=f"Em dash found in {field_name}. Replace with colon, comma, or spaced hyphen.",
            )
        )


def _check_trademark_wording(issues: list[ValidationIssue], field_name: str, text: str) -> None:
    if "roblox" in text.lower():
        issues.append(
            ValidationIssue(
                severity="warning",
                code="TRADEMARK_IN_VISUAL",
                message=(
                    f"Raw word 'Roblox' found in {field_name}. Use descriptive blocky 3D plastic "
                    "avatar wording in visual prompts to avoid Google Flow safety rejections."
                ),
            )
        )


def validate_episode(ep: EpisodeSpec) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    char_handles: set[str] = set()
    loc_handles: set[str] = set()

    _check_em_dash(issues, "title_id", ep.title_id)
    _check_em_dash(issues, "world_rule_id", ep.world_rule_id)
    _check_em_dash(issues, "style_bible", ep.style_bible)
    _check_trademark_wording(issues, "style_bible", ep.style_bible)

    for c in ep.characters:
        if not HANDLE_RE.match(c.handle):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_HANDLE",
                    message=f"Character handle '{c.handle}' must be @PascalCase with no spaces or punctuation.",
                )
            )
        if c.handle in char_handles:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_HANDLE",
                    message=f"Duplicate character handle '{c.handle}'.",
                )
            )
        char_handles.add(c.handle)
        _check_em_dash(issues, f"character {c.handle}", f"{c.visual_description} {c.wardrobe}")
        _check_trademark_wording(issues, f"character {c.handle}", c.visual_description)

    for loc in ep.locations:
        if not HANDLE_RE.match(loc.handle):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="INVALID_HANDLE",
                    message=f"Location handle '{loc.handle}' must be @PascalCase with no spaces or punctuation.",
                )
            )
        if loc.handle in loc_handles or loc.handle in char_handles:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DUPLICATE_HANDLE",
                    message=f"Duplicate handle '{loc.handle}' across characters/locations.",
                )
            )
        loc_handles.add(loc.handle)
        _check_em_dash(issues, f"location {loc.handle}", loc.visual_description)
        _check_trademark_wording(issues, f"location {loc.handle}", loc.visual_description)

    all_handles = char_handles | loc_handles

    expected_numbers = list(range(1, len(ep.scenes) + 1))
    actual_numbers = [s.scene_number for s in ep.scenes]
    if actual_numbers != expected_numbers:
        issues.append(
            ValidationIssue(
                severity="error",
                code="SCENE_NUMBERING",
                message=f"Scene numbers must be sequential {expected_numbers}, got {actual_numbers}.",
            )
        )

    if ep.scenes:
        first = ep.scenes[0]
        if first.beat != "hook":
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="HOOK_BEAT",
                    message="Scene 1 should use beat='hook' for strong short-form retention.",
                )
            )
        lowered_hook = first.narration_id.strip().lower()
        valid_prefixes = (
            ("di dunia", "di kota", "di taman", "halo", "yuk", "lihat")
            if ep.content_mode == "kids_animation_id"
            else ("di dunia ini", "di kota ini")
        )
        if not lowered_hook.startswith(valid_prefixes):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="HOOK_PHRASE",
                    message=(
                        "Scene 1 narration ideally opens with a strong hook phrase "
                        f"({', '.join(valid_prefixes[:2])}...)."
                    ),
                )
            )

    for scene in ep.scenes:
        prefix = f"scene {scene.scene_number}"
        _check_em_dash(issues, f"{prefix}.narration_id", scene.narration_id)
        _check_em_dash(issues, f"{prefix}.visual_prompt", scene.visual_prompt)
        _check_trademark_wording(issues, f"{prefix}.visual_prompt", scene.visual_prompt)

        if scene.location not in loc_handles:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="UNKNOWN_LOCATION",
                    message=f"{prefix} references unknown location '{scene.location}'.",
                )
            )

        for ch in scene.characters:
            if ch not in char_handles:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="UNKNOWN_CHARACTER",
                        message=f"{prefix} references unknown character '{ch}'.",
                    )
                )

        mentioned = set(HANDLE_MENTION_RE.findall(scene.visual_prompt))
        for m in sorted(mentioned):
            if m not in all_handles:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="UNDECLARED_HANDLE_IN_PROMPT",
                        message=f"{prefix}.visual_prompt mentions undeclared handle '{m}'.",
                    )
                )

        required_in_prompt = set(scene.characters) | {scene.location}
        missing = sorted(required_in_prompt - mentioned)
        if missing:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="MISSING_HANDLE_IN_PROMPT",
                    message=(
                        f"{prefix}.visual_prompt must explicitly include declared handles: "
                        f"{', '.join(missing)}."
                    ),
                )
            )

    if ep.total_duration_seconds > 32:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="DURATION_LONG",
                message=f"Total duration is {ep.total_duration_seconds}s (> 32s). Keep meme shorts snappy.",
            )
        )
    elif ep.total_duration_seconds < 12:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="DURATION_SHORT",
                message=f"Total duration is {ep.total_duration_seconds}s (< 12s).",
            )
        )

    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == "error" for i in issues)
