from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal

import yaml

from roblox_meme_flow.credit_guard import BUDGET_PRESETS
from roblox_meme_flow.models import EpisodeSpec, load_episode
from roblox_meme_flow.researcher import ViralResearchBrief, build_viral_research_brief
from roblox_meme_flow.validator import has_errors, validate_episode

JAKARTA_TZ = dt.timezone(dt.timedelta(hours=7), "WIB")

VOICE_PRESETS: dict[str, dict[str, object]] = {
    "preset_a": {
        "label": "Preset A - Cowok High-Pitch Lucu (Default Meme)",
        "tts_voice": "id-ID-ArdiNeural",
        "tts_rate": "+16%",
        "tts_pitch": "+28Hz",
        "tts_pitch_shift": 1.18,
    },
    "preset_b": {
        "label": "Preset B - Cewek TikTok Enerjik",
        "tts_voice": "id-ID-GadisNeural",
        "tts_rate": "+16%",
        "tts_pitch": "+22Hz",
        "tts_pitch_shift": 1.12,
    },
    "preset_c": {
        "label": "Preset C - Chipmunk Shitpost Super Cempreng",
        "tts_voice": "id-ID-ArdiNeural",
        "tts_rate": "+18%",
        "tts_pitch": "+40Hz",
        "tts_pitch_shift": 1.30,
    },
    "preset_d": {
        "label": "Preset D - Ceria Animasi Anak-Anak",
        "tts_voice": "id-ID-GadisNeural",
        "tts_rate": "+10%",
        "tts_pitch": "+24Hz",
        "tts_pitch_shift": 1.12,
    },
}


def list_existing_episode_summaries(episodes_dir: Path) -> list[str]:
    summaries: list[str] = []
    if not episodes_dir.exists():
        return summaries
    for path in sorted(episodes_dir.glob("*.yaml")):
        try:
            ep = load_episode(path)
            summaries.append(f"- {path.name}: {ep.title_id} ({ep.world_rule_id})")
        except Exception:
            summaries.append(f"- {path.name}")
    return summaries


def build_t3_generation_prompt(
    project_root: Path,
    content_mode: Literal["meme_roblox_id", "kids_animation_id"] = "meme_roblox_id",
    budget_preset: str = "hemat_50",
    voice_preset: str = "preset_a",
    topic_hint: str = "",
    bgm_path: str = "assets/bgm/in_this_town_bgm.mp3",
    research_brief: ViralResearchBrief | None = None,
) -> tuple[str, ViralResearchBrief]:
    brief = research_brief or build_viral_research_brief(
        content_mode=content_mode, topic_hint=topic_hint, fetch_live=True
    )
    budget = BUDGET_PRESETS.get(budget_preset, BUDGET_PRESETS["hemat_50"])
    voice = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["preset_a"])
    existing = list_existing_episode_summaries(project_root / "episodes")
    today_str = dt.datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d")

    skill_rel = (
        ".agents/skills/kids-animation-id/SKILL.md"
        if content_mode == "kids_animation_id"
        else ".agents/skills/di-dunia-ini-roblox-id/SKILL.md"
    )
    existing_block = "\n".join(existing) if existing else "- (belum ada episode)"

    prompt = f"""Buat 1 episode YAML baru yang siap viral untuk YouTube Shorts, TikTok, dan Instagram Reels!

Ikuti skill: `{skill_rel}` dan `.agents/skills/google-flow-scripting/SKILL.md`.

{brief.to_prompt_block()}

## Constraint Wajib (Budget Kredit & Teknis)
- Tanggal WIB: `{today_str}` (gunakan prefix `episode_id: "{today_str}-..."`)
- `content_mode: "{content_mode}"`
- Budget preset `{budget_preset}`: WAJIB tepat **{budget['scenes']} scene**, masing-masing `duration_seconds: {budget['duration_seconds']}`, `video_model: "{budget['video_model']}"` (estimasi **{budget['estimated_credits']} kredit** agar muat 1 video/hari dari top-up +50 kredit harian Google Flow!).
- `aspect_ratio: "9:16"`, `image_model: "nano-2.1"`
- Audio preset:
  - `tts_voice: "{voice['tts_voice']}"`
  - `tts_rate: "{voice['tts_rate']}"`
  - `tts_pitch: "{voice['tts_pitch']}"`
  - `tts_pitch_shift: {voice['tts_pitch_shift']}`
  - `bgm_path: "{bgm_path}"`
  - `bgm_volume: 0.16`
- Semua karakter dan lokasi wajib `@PascalCase` unik dan WAJIB disebut eksplisit di setiap `scene.visual_prompt`.
- DILARANG memakai em dash (`—`) di mana pun.
- DILARANG menulis kata merek `Roblox`, `Pixar`, `Disney`, `Cocomelon` di `style_bible` atau `visual_prompt` (deskripsikan gaya visual blocky/toy 3D secara deskriptif).
- `narration_id` berbahasa Indonesia natural, singkat (pas dibaca dalam {budget['duration_seconds']} detik per scene!), punchy, dan cocok dengan algoritma YT Shorts + TikTok + IG Reels.
- Jangan duplikat ide dari episode yang sudah ada di bawah ini:
{existing_block}

## Format Output
Kembalikan HANYA 1 blok ```yaml ... ``` valid yang langsung lulus `EpisodeSpec` (tanpa teks tambahan di luar blok YAML).
"""
    return prompt, brief


def extract_yaml_block(text: str) -> str:
    fenced = re.findall(r"```(?:yaml|yml)\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[-1].strip()
    generic = re.findall(r"```\s*\n(.*?)```", text, flags=re.DOTALL)
    if generic:
        return generic[-1].strip()
    # Fallback: find first line starting with episode_id:
    idx = text.find("episode_id:")
    if idx != -1:
        return text[idx:].strip()
    return text.strip()


def validate_and_save_yaml(yaml_text: str, episodes_dir: Path, filename: str | None = None) -> dict[str, object]:
    clean_yaml = extract_yaml_block(yaml_text)
    parsed = yaml.safe_load(clean_yaml)
    ep = EpisodeSpec.model_validate(parsed)
    issues = validate_episode(ep)
    if has_errors(issues):
        raise ValueError(
            "Validasi gagal:\n" + "\n".join(f"[{i.severity.upper()}] {i.code}: {i.message}" for i in issues)
        )

    episodes_dir.mkdir(parents=True, exist_ok=True)
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", ep.episode_id).strip("_").lower()
    target_name = filename or f"{safe_slug}.yaml"
    if not target_name.endswith(".yaml"):
        target_name += ".yaml"
    target_path = episodes_dir / Path(target_name).name
    target_path.write_text(clean_yaml.strip() + "\n", encoding="utf-8")
    return {
        "filename": target_path.name,
        "path": str(target_path),
        "episode_id": ep.episode_id,
        "title_id": ep.title_id,
        "warnings": [{"code": i.code, "message": i.message} for i in issues if i.severity == "warning"],
    }


def generate_script_via_kilo(
    project_root: Path,
    prompt: str,
    model: str = "openai/gpt-6.2-sol",
    timeout_s: int = 180,
) -> dict[str, object]:
    kilo_bin = shutil.which("kilo") or shutil.which("kilocode")
    if not kilo_bin:
        raise RuntimeError(
            "Kilo CLI tidak ditemukan di PATH. Gunakan tombol 'Salin Prompt ke T3 Code' lalu paste YAML hasil T3 ke editor."
        )

    cmd = [kilo_bin, "run", "--dir", str(project_root)]
    if model.strip():
        cmd.extend(["-m", model.strip()])
    cmd.append(prompt)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout)[-1200:]
        raise RuntimeError(
            f"Kilo CLI gagal (exit {proc.returncode}) dengan model '{model}'. "
            f"Coba ganti model (misal ai_mas_wayan/gpt-6.2-sol) atau gunakan T3 Code Bridge.\nDetail: {err}"
        )

    saved = validate_and_save_yaml(proc.stdout, project_root / "episodes")
    return saved
