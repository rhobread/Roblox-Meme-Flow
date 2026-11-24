from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from roblox_meme_flow.layout import EpisodeLayout
from roblox_meme_flow.models import EpisodeSpec


def _grid_for_panel_count(count: int) -> str:
    if count <= 3:
        return f"1x{count}"
    if count == 4:
        return "2x2"
    if count <= 6:
        return "2x3"
    return "3x3"


def build_reference_prompts(ep: EpisodeSpec) -> dict[str, str]:
    prompts: dict[str, str] = {}
    for ch in ep.characters:
        prompts[ch.handle] = (
            f"Character reference sheet for {ch.handle}. {ep.style_bible} "
            f"Subject: {ch.visual_description}. Wardrobe: {ch.wardrobe}. "
            f"Default expression: {ch.expression_default}. "
            "Clean neutral studio background, full-body front view and 3/4 view, "
            "consistent proportions, no text or labels."
        )
    for loc in ep.locations:
        props = ", ".join(loc.key_props) if loc.key_props else "minimal clean background props"
        prompts[loc.handle] = (
            f"Environment reference still for {loc.handle}. {ep.style_bible} "
            f"Setting: {loc.visual_description}. Lighting: {loc.lighting}. "
            f"Key props: {props}. Empty establishing view without extra characters, no text."
        )
    return prompts


def build_storyboard_prompt(ep: EpisodeSpec) -> str:
    panel_count = len(ep.scenes)
    grid = _grid_for_panel_count(panel_count)
    panel_lines = []
    for s in ep.scenes:
        cast_str = ", ".join(s.characters) if s.characters else "no characters"
        panel_lines.append(
            f"Panel {s.scene_number} ({s.beat}, {s.duration_seconds}s): "
            f"Location {s.location}; Cast {cast_str}; Camera: {s.camera}; "
            f"Action: {s.visual_prompt}"
        )

    panels_block = "\n".join(panel_lines)
    return (
        "GENERATE THE STORYBOARD IMAGE NOW.\n"
        f"Create exactly {panel_count} distinct vertical storyboard panels arranged in a clean "
        f"{grid} contact-sheet grid with thin white borders and zero text, zero speech bubbles, "
        "and zero watermarks. Do not reply with a plan or description; output the image directly. "
        "Do not invent extra characters, wardrobe changes, props, or background crowds.\n\n"
        f"Style bible: {ep.style_bible}\n\n"
        f"{panels_block}\n"
    )


def build_scene_video_prompts(ep: EpisodeSpec) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for s in ep.scenes:
        full_prompt = (
            f"{ep.style_bible} "
            f"Scene {s.scene_number} ({s.duration_seconds}s, {ep.aspect_ratio}): "
            f"{s.visual_prompt} "
            f"Camera: {s.camera}. "
            f"Audio and SFX: {s.audio_sfx}. "
            "No spoken dialogue on screen, no floating captions, no text overlays."
        )
        items.append(
            {
                "scene_number": s.scene_number,
                "beat": s.beat,
                "duration_seconds": s.duration_seconds,
                "video_model": ep.video_model,
                "aspect_ratio": ep.aspect_ratio,
                "references": [*s.characters, s.location],
                "prompt": full_prompt,
                "narration_id": s.narration_id,
            }
        )
    return items


def _fmt_srt_time(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_caption_chunks(text: str, max_words: int = 5) -> list[str]:
    words = text.strip().split()
    if not words:
        return []
    chunks = []
    for idx in range(0, len(words), max_words):
        chunks.append(" ".join(words[idx : idx + max_words]))
    return chunks


def build_srt(ep: EpisodeSpec) -> str:
    entries: list[str] = []
    cursor = 0.0
    counter = 1

    for scene in ep.scenes:
        caption_source = scene.subtitle_override or scene.narration_id
        chunks = _split_caption_chunks(caption_source, max_words=5)
        if not chunks:
            cursor += float(scene.duration_seconds)
            continue

        chunk_dur = float(scene.duration_seconds) / len(chunks)
        for chunk in chunks:
            start = cursor
            end = min(cursor + chunk_dur, cursor + float(scene.duration_seconds))
            # Avoid zero-length cues
            if math.isclose(start, end):
                end = start + 0.5
            entries.append(
                f"{counter}\n{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}\n{chunk.upper()}\n"
            )
            cursor = end
            counter += 1

    return "\n".join(entries).strip() + "\n"


def export_plan(ep: EpisodeSpec, out_dir: Path, source_yaml: Path | None = None) -> Path:
    layout = EpisodeLayout.for_episode(out_dir, ep.episode_id)
    layout.ensure_dirs()

    refs = build_reference_prompts(ep)
    storyboard = build_storyboard_prompt(ep)
    scene_prompts = build_scene_video_prompts(ep)
    srt_content = build_srt(ep)

    plan_payload = {
        "episode_id": ep.episode_id,
        "title_id": ep.title_id,
        "world_rule_id": ep.world_rule_id,
        "aspect_ratio": ep.aspect_ratio,
        "image_model": ep.image_model,
        "video_model": ep.video_model,
        "total_duration_seconds": ep.total_duration_seconds,
        "reference_prompts": refs,
        "storyboard_prompt": storyboard,
        "scene_prompts": scene_prompts,
    }

    (layout.scripts_dir / "plan.json").write_text(
        json.dumps(plan_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (layout.scripts_dir / "storyboard_prompt.txt").write_text(storyboard, encoding="utf-8")
    (layout.subtitles_dir / "captions.srt").write_text(srt_content, encoding="utf-8")
    if source_yaml and source_yaml.exists():
        shutil.copy2(source_yaml, layout.scripts_dir / source_yaml.name)

    md_lines = [
        f"# Production Sheet: {ep.title_id}",
        "",
        f"- **Episode ID:** `{ep.episode_id}`",
        f"- **Rule:** {ep.world_rule_id}",
        f"- **Duration:** {ep.total_duration_seconds}s ({ep.aspect_ratio})",
        f"- **Image Model:** `{ep.image_model}` | **Video Model:** `{ep.video_model}`",
        "",
        "## 1. Reference Images (0 Flow Credits)",
        "",
    ]
    for handle, prompt in refs.items():
        md_lines.extend([f"### {handle}", "", "```text", prompt, "```", ""])

    md_lines.extend(
        [
            "## 2. Storyboard Contact Sheet (Approve Before Video)",
            "",
            "```text",
            storyboard.strip(),
            "```",
            "",
            "## 3. Video Scene Prompts",
            "",
        ]
    )
    for item in scene_prompts:
        md_lines.extend(
            [
                f"### Scene {item['scene_number']} ({item['beat']}, {item['duration_seconds']}s)",
                f"- **Narasi ID:** {item['narration_id']}",
                f"- **References:** {', '.join(item['references'])}",
                "",
                "```text",
                str(item["prompt"]),
                "```",
                "",
            ]
        )

    (layout.scripts_dir / "scene_prompts.md").write_text("\n".join(md_lines), encoding="utf-8")
    return layout.root
