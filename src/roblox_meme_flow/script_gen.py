from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Literal

import yaml

from roblox_meme_flow.credit_guard import BUDGET_PRESETS
from roblox_meme_flow.models import EpisodeSpec, load_episode
from roblox_meme_flow.researcher import ViralResearchBrief, build_viral_research_brief
from roblox_meme_flow.validator import HANDLE_MENTION_RE, has_errors, validate_episode
from roblox_meme_flow.win_silent import silent_subprocess_kwargs

JAKARTA_TZ = dt.timezone(dt.timedelta(hours=7), "WIB")

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

VALID_BEATS = {"hook", "setup", "escalation", "complication", "climax", "twist", "outro"}
BEAT_ALIASES: dict[str, str] = {
    "intro": "hook",
    "opening": "hook",
    "start": "hook",
    "conflict": "complication",
    "problem": "complication",
    "build": "escalation",
    "buildup": "escalation",
    "rising": "escalation",
    "aftermath": "escalation",
    "payoff": "twist",
    "reveal": "twist",
    "plot_twist": "twist",
    "ending": "outro",
    "resolution": "outro",
    "punchline": "outro",
    "cta": "outro",
}
VALID_DURATIONS = (3, 4, 5, 6, 8, 10)

AI_ENGINES: dict[str, dict[str, str]] = {
    "antigravity": {
        "label": "Google Antigravity (Gemini 4 Neon High - Rekomendasi Utama)",
        "default_model": "gemini-4-neon",
    },
    "kilo_free": {
        "label": "Kilo AI Gratis (Cadangan Tanpa Login)",
        "default_model": "kilo/kilo-auto/free",
    },
    "kilo_custom": {
        "label": "Kilo AI - Model Lain (Custom)",
        "default_model": "kilo/nvidia/nemotron-3-ultra-550b-a55b:free",
    },
}

VOICE_PRESETS: dict[str, dict[str, object]] = {
    "preset_a": {
        "label": "Preset A - Cowok High-Pitch Lucu Cepat (Default Meme)",
        "tts_voice": "id-ID-ArdiNeural",
        "tts_rate": "+18%",
        "tts_pitch": "+28Hz",
        "tts_pitch_shift": 1.18,
    },
    "preset_b": {
        "label": "Preset B - Cewek TikTok Enerjik Cepat",
        "tts_voice": "id-ID-GadisNeural",
        "tts_rate": "+18%",
        "tts_pitch": "+22Hz",
        "tts_pitch_shift": 1.12,
    },
    "preset_c": {
        "label": "Preset C - Chipmunk Shitpost Super Cempreng",
        "tts_voice": "id-ID-ArdiNeural",
        "tts_rate": "+20%",
        "tts_pitch": "+40Hz",
        "tts_pitch_shift": 1.30,
    },
    "preset_d": {
        "label": "Preset D - Ceria Animasi Anak-Anak",
        "tts_voice": "id-ID-GadisNeural",
        "tts_rate": "+12%",
        "tts_pitch": "+24Hz",
        "tts_pitch_shift": 1.12,
    },
}


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text or "")


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
    budget_preset: str = "long_veo_80",
    voice_preset: str = "preset_a",
    topic_hint: str = "",
    bgm_path: str = "assets/bgm/in_this_town_bgm.mp3",
    research_brief: ViralResearchBrief | None = None,
) -> tuple[str, ViralResearchBrief]:
    brief = research_brief or build_viral_research_brief(
        content_mode=content_mode, topic_hint=topic_hint, fetch_live=True
    )
    budget = BUDGET_PRESETS.get(budget_preset, BUDGET_PRESETS["long_veo_80"])
    voice = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["preset_a"])
    existing = list_existing_episode_summaries(project_root / "episodes")
    today_str = dt.datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d")

    skill_rel = (
        ".agents/skills/kids-animation-id/SKILL.md"
        if content_mode == "kids_animation_id"
        else ".agents/skills/di-dunia-ini-roblox-id/SKILL.md"
    )
    existing_block = "\n".join(existing) if existing else "- (belum ada episode)"
    num_scenes = int(budget["scenes"])
    dur_per_scene = int(budget["duration_seconds"])
    words_target = max(10, int(dur_per_scene * 3.0))

    style_note = (
        "Vibrant stylized 3D toy-like cartoon animation for children, soft glossy rounded characters with big friendly eyes, sunny pastel storybook colors, zero violence, 100% YouTube Kids safe."
        if content_mode == "kids_animation_id"
        else "Stylized 3D blocky plastic game-avatar animation, smooth glossy toy-like R6/R15 cubic characters with expressive printed deadpan faces, bright clean indie-game lighting, Indonesian daily comedy."
    )
    hook_note = (
        'Scene 1 narration_id WAJIB dimulai dengan "Di dunia..." atau "Halo teman-teman..." atau "Yuk lihat..." yang ceria.'
        if content_mode == "kids_animation_id"
        else 'Scene 1 narration_id WAJIB dimulai dengan "Di dunia ini, ..." diikuti 1 aturan absurd lucu ala Indonesia.'
    )

    prompt = f"""Buat 1 episode YAML baru yang FAST-PACED (pacing cepat, banyak scene, zero jeda bosan) dan siap viral untuk YouTube Shorts, TikTok, dan Instagram Reels!

Skill referensi: `{skill_rel}` dan `.agents/skills/google-flow-scripting/SKILL.md`.

{brief.to_prompt_block()}

## Constraint Wajib
- Tanggal WIB: `{today_str}` (gunakan prefix `episode_id: "{today_str}-..."` yang unik, huruf kecil + tanda hubung saja)
- `content_mode: "{content_mode}"`
- Budget preset `{budget_preset}`: WAJIB tepat **{num_scenes} scene**, masing-masing `duration_seconds: {dur_per_scene}`, `video_model: "{budget['video_model']}"` (estimasi **{budget['estimated_credits']} kredit**).
- Nilai `beat` yang valid HANYA: `hook`, `setup`, `escalation`, `complication`, `climax`, `twist`, `outro`.
- {hook_note}
- Tulis `narration_id` berbahasa Indonesia lincah, natural, lucu/seru, mengisi durasi tiap scene (~{words_target} kata per scene).
- Tulis `visual_prompt`, `camera`, `audio_sfx`, `visual_description`, `wardrobe`, `lighting` dalam Bahasa Inggris yang jelas & hidup.
- Gaya visual: {style_note}
- Semua karakter (2-3 karakter) dan lokasi (1-2 lokasi) WAJIB punya `handle` format `@PascalCase` tanpa spasi/underscore (contoh: `@BudiKos`, `@PakRT`, `@WarkopMalam`).
- Setiap `scene.visual_prompt` WAJIB menyebut eksplisit SEMUA `@Handle` yang ada di `scene.characters` dan `scene.location` scene tersebut, dan JANGAN menyebut `@Handle` lain yang belum dideklarasikan.
- Maksimal 2 karakter + 1 lokasi per scene jika `video_model` adalah `veo-lite`.
- DILARANG memakai em dash (`—`) di mana pun. Gunakan koma atau tanda hubung biasa `-`.
- DILARANG menulis kata merek `Roblox`, `Pixar`, `Disney`, `Cocomelon` di `style_bible`, `visual_description`, atau `visual_prompt`.
- Jangan duplikat ide dari episode yang sudah ada:
{existing_block}

## Schema YAML Wajib (Ikuti Persis Nama Field Ini!)
```yaml
episode_id: "{today_str}-judul-singkat"
title_id: "Judul Menarik Bahasa Indonesia"
world_rule_id: "Satu kalimat aturan dunia / premis utama dalam Bahasa Indonesia."
content_mode: "{content_mode}"
aspect_ratio: "9:16"
image_model: "nano-2.1"
video_model: "{budget['video_model']}"
tts_voice: "{voice['tts_voice']}"
tts_rate: "{voice['tts_rate']}"
tts_pitch: "{voice['tts_pitch']}"
tts_pitch_shift: {voice['tts_pitch_shift']}
bgm_path: "{bgm_path}"
bgm_volume: 0.16
fast_cut_sync: true
scene_gap_seconds: 0.10
characters:
  - handle: "@TokohSatu"
    role: "Peran singkat"
    visual_description: "Blocky 3D plastic toy avatar, ..."
    wardrobe: "Outfit details in English"
    expression_default: "expressive printed plastic face"
locations:
  - handle: "@LokasiSatu"
    visual_description: "Colorful 3D plastic blocky Indonesian setting in English..."
    lighting: "bright clean lighting"
    key_props:
      - "prop 1"
scenes:
  - scene_number: 1
    beat: "hook"
    duration_seconds: {dur_per_scene}
    characters:
      - "@TokohSatu"
    location: "@LokasiSatu"
    narration_id: "Narasi Bahasa Indonesia yang padat dan menarik..."
    visual_prompt: "In @LokasiSatu, @TokohSatu does an expressive action..."
    camera: "punchy vertical medium close-up"
    audio_sfx: "comedic pop, ambient sound"
```

## Format Output
Kembalikan HANYA 1 blok ```yaml ... ``` lengkap dengan tepat {num_scenes} scene (tanpa penjelasan atau teks lain di luar blok YAML).
"""
    return prompt, brief


def extract_yaml_block(text: str) -> str:
    clean = strip_ansi(text)
    fenced = re.findall(r"```(?:yaml|yml)\s*\n(.*?)```", clean, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[-1].strip()
    generic = re.findall(r"```\s*\n(.*?)```", clean, flags=re.DOTALL)
    if generic:
        return generic[-1].strip()
    idx = clean.find("episode_id:")
    if idx != -1:
        return clean[idx:].strip()
    return clean.strip()


def _clean_text_dashes(val: object) -> str:
    s = str(val or "")
    s = s.replace("\u2014", ", ").replace("\u2013", "-")
    return re.sub(r"\s{2,}", " ", s).strip()


def _strip_trademarks(text: str) -> str:
    cleaned = re.sub(r"\broblox\b", "blocky 3D plastic toy", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(pixar|disney|cocomelon)\b", "stylized 3D cartoon", cleaned, flags=re.IGNORECASE)
    return cleaned


def _normalize_handle(raw: str, fallback: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(raw or ""))
    if not parts:
        return fallback
    pascal = "".join(p[0].upper() + p[1:] for p in parts if p)
    if not pascal or not pascal[0].isalpha():
        pascal = "Ref" + pascal
    return "@" + pascal


def _closest_duration(raw: object) -> int:
    try:
        n = int(float(str(raw)))
    except Exception:
        return 6
    return min(VALID_DURATIONS, key=lambda d: abs(d - n))


def sanitize_episode_dict(parsed: object) -> dict[str, object]:
    """Normalize minor LLM output quirks before strict EpisodeSpec & continuity validation."""
    if not isinstance(parsed, dict):
        raise ValueError("Output AI bukan struktur YAML episode yang valid.")

    data = dict(parsed)
    for key in ("episode_id", "title_id", "world_rule_id"):
        if key in data:
            data[key] = _clean_text_dashes(data[key])
    if "style_bible" in data and data["style_bible"]:
        data["style_bible"] = _strip_trademarks(_clean_text_dashes(data["style_bible"]))

    # Normalize characters and track handle remapping
    handle_map: dict[str, str] = {}
    used_handles: set[str] = set()
    raw_chars = data.get("characters")
    norm_chars: list[dict[str, object]] = []
    if isinstance(raw_chars, list):
        for idx, ch in enumerate(raw_chars, start=1):
            if not isinstance(ch, dict):
                continue
            orig = str(ch.get("handle", "")).strip()
            h = _normalize_handle(orig, f"@Tokoh{idx}")
            while h in used_handles:
                h = f"{h}{idx}"
            used_handles.add(h)
            if orig:
                handle_map[orig] = h
                handle_map[orig.lstrip("@")] = h
            norm_chars.append(
                {
                    "handle": h,
                    "role": _clean_text_dashes(ch.get("role") or f"Karakter {idx}"),
                    "visual_description": _strip_trademarks(
                        _clean_text_dashes(
                            ch.get("visual_description")
                            or "Blocky 3D plastic toy avatar with glossy cubic body and expressive printed face"
                        )
                    ),
                    "wardrobe": _strip_trademarks(_clean_text_dashes(ch.get("wardrobe") or "casual colorful outfit")),
                    "expression_default": _clean_text_dashes(
                        ch.get("expression_default") or "deadpan wide-eyed plastic stare"
                    ),
                }
            )
    data["characters"] = norm_chars
    char_handles = {str(c["handle"]) for c in norm_chars}

    # Normalize locations
    raw_locs = data.get("locations")
    norm_locs: list[dict[str, object]] = []
    if isinstance(raw_locs, list):
        for idx, loc in enumerate(raw_locs, start=1):
            if not isinstance(loc, dict):
                continue
            orig = str(loc.get("handle", "")).strip()
            h = _normalize_handle(orig, f"@Lokasi{idx}")
            while h in used_handles:
                h = f"{h}Loc{idx}"
            used_handles.add(h)
            if orig:
                handle_map[orig] = h
                handle_map[orig.lstrip("@")] = h
            props = loc.get("key_props")
            norm_props = [_clean_text_dashes(p) for p in props] if isinstance(props, list) else []
            norm_locs.append(
                {
                    "handle": h,
                    "visual_description": _strip_trademarks(
                        _clean_text_dashes(
                            loc.get("visual_description")
                            or "Colorful 3D blocky plastic Indonesian neighborhood setting"
                        )
                    ),
                    "lighting": _clean_text_dashes(loc.get("lighting") or "bright clean daylight"),
                    "key_props": norm_props,
                }
            )
    data["locations"] = norm_locs
    loc_handles = {str(loc["handle"]) for loc in norm_locs}
    all_handles = char_handles | loc_handles
    default_char = next(iter(char_handles), None)
    default_loc = next(iter(loc_handles), None)

    is_veo_lite = str(data.get("video_model", "")).strip().lower().startswith("veo-")

    # Normalize scenes
    raw_scenes = data.get("scenes")
    norm_scenes: list[dict[str, object]] = []
    if isinstance(raw_scenes, list):
        total = len(raw_scenes)
        for idx, sc in enumerate(raw_scenes, start=1):
            if not isinstance(sc, dict):
                continue
            raw_beat = str(sc.get("beat", "")).strip().lower()
            if raw_beat in VALID_BEATS:
                beat = raw_beat
            elif raw_beat in BEAT_ALIASES:
                beat = BEAT_ALIASES[raw_beat]
            elif idx == 1:
                beat = "hook"
            elif idx == total:
                beat = "outro"
            else:
                beat = "escalation"

            # Remap scene characters
            sc_chars_raw = sc.get("characters") or []
            if isinstance(sc_chars_raw, str):
                sc_chars_raw = [sc_chars_raw]
            sc_chars: list[str] = []
            for c_ref in sc_chars_raw:
                mapped = handle_map.get(str(c_ref).strip()) or handle_map.get(str(c_ref).strip().lstrip("@"))
                if mapped and mapped in char_handles and mapped not in sc_chars:
                    sc_chars.append(mapped)
            if not sc_chars and default_char:
                sc_chars = [default_char]
            if is_veo_lite and len(sc_chars) > 2:
                sc_chars = sc_chars[:2]

            # Remap scene location
            loc_raw = str(sc.get("location", "")).strip()
            sc_loc = handle_map.get(loc_raw) or handle_map.get(loc_raw.lstrip("@"))
            if not sc_loc or sc_loc not in loc_handles:
                sc_loc = default_loc or "@Lokasi1"

            vp = _strip_trademarks(_clean_text_dashes(sc.get("visual_prompt") or ""))
            # Replace remapped handles in visual_prompt
            for old_h, new_h in handle_map.items():
                if old_h.startswith("@") and old_h != new_h:
                    vp = vp.replace(old_h, new_h)

            # Strip any undeclared @Handles in visual_prompt
            def _fix_mention(match: re.Match[str]) -> str:
                tok = match.group(0)
                if tok in all_handles:
                    return tok
                mapped = handle_map.get(tok) or handle_map.get(tok.lstrip("@"))
                if mapped and mapped in all_handles:
                    return mapped
                return tok.lstrip("@")

            vp = HANDLE_MENTION_RE.sub(_fix_mention, vp)

            # Ensure all declared scene characters and location appear in visual_prompt
            mentioned = set(HANDLE_MENTION_RE.findall(vp))
            missing_chars = [c for c in sc_chars if c not in mentioned]
            missing_loc = sc_loc if sc_loc not in mentioned else None
            prefix_parts: list[str] = []
            if missing_loc:
                prefix_parts.append(f"In {missing_loc}")
            if missing_chars:
                prefix_parts.append("with " + " and ".join(missing_chars))
            if prefix_parts:
                vp = f"{', '.join(prefix_parts)}, {vp}" if vp else f"{', '.join(prefix_parts)}."

            narration = _clean_text_dashes(sc.get("narration_id") or "")
            scene_obj: dict[str, object] = {
                "scene_number": idx,
                "beat": beat,
                "duration_seconds": _closest_duration(sc.get("duration_seconds", 6)),
                "characters": sc_chars,
                "location": sc_loc,
                "narration_id": narration,
                "visual_prompt": vp,
                "camera": _clean_text_dashes(sc.get("camera") or "dynamic vertical medium shot"),
                "audio_sfx": _clean_text_dashes(sc.get("audio_sfx") or "subtle ambient sound, comedic pop"),
            }
            if sc.get("subtitle_override"):
                scene_obj["subtitle_override"] = _clean_text_dashes(sc["subtitle_override"])
            norm_scenes.append(scene_obj)
    data["scenes"] = norm_scenes

    return data


def validate_and_save_yaml(
    yaml_text: str,
    episodes_dir: Path,
    filename: str | None = None,
    *,
    auto_sanitize: bool = False,
) -> dict[str, object]:
    clean_yaml = extract_yaml_block(yaml_text)
    parsed = yaml.safe_load(clean_yaml)
    if auto_sanitize:
        parsed = sanitize_episode_dict(parsed)
        clean_yaml = yaml.safe_dump(parsed, allow_unicode=True, sort_keys=False)

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


def _invoke_kilo_once(kilo_bin: str, project_root: Path, model: str, prompt: str, timeout_s: int) -> str:
    cmd = [kilo_bin, "run", "--agent", "ask", "--dir", str(project_root)]
    if model.strip():
        cmd.extend(["-m", model.strip()])

    proc = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=False,
        **silent_subprocess_kwargs(),
    )
    if proc.returncode != 0:
        err = strip_ansi(proc.stderr or proc.stdout).strip()[-1000:]
        low = err.lower()
        if "sign in" in low or "not supported" in low or "unauthorized" in low:
            raise RuntimeError(
                f"Model '{model}' butuh login / tidak didukung akun saat ini. "
                "Gunakan mesin default 'Otomatis - Kilo AI Gratis' (kilo/kilo-auto/free)."
            )
        raise RuntimeError(f"Kilo AI gagal (exit {proc.returncode}) dengan model '{model}':\n{err}")
    return proc.stdout


def generate_script_via_kilo(
    project_root: Path,
    prompt: str,
    model: str = "kilo/kilo-auto/free",
    timeout_s: int = 180,
    log_callback=None,
) -> dict[str, object]:
    kilo_bin = shutil.which("kilo") or shutil.which("kilocode")
    if not kilo_bin:
        raise RuntimeError(
            "Kilo CLI tidak ditemukan di komputer ini. Install Kilo CLI atau gunakan mode manual Salin Prompt."
        )

    effective_model = model.strip() or "kilo/kilo-auto/free"
    raw_output = _invoke_kilo_once(kilo_bin, project_root, effective_model, prompt, timeout_s)
    try:
        return validate_and_save_yaml(raw_output, project_root / "episodes", auto_sanitize=True)
    except Exception as first_err:
        if log_callback:
            log_callback("      Format YAML perlu dirapikan otomatis, mencoba perbaikan cepat (1/1)...")
        repair_prompt = (
            "Perbaiki YAML di bawah ini agar 100% valid mengikuti schema EpisodeSpec dan kembalikan "
            "HANYA 1 blok ```yaml ... ``` tanpa teks tambahan.\n\n"
            f"Error validasi:\n{first_err}\n\n"
            f"YAML sebelumnya:\n{strip_ansi(raw_output)[-4500:]}"
        )
        repaired_output = _invoke_kilo_once(kilo_bin, project_root, effective_model, repair_prompt, timeout_s)
        return validate_and_save_yaml(repaired_output, project_root / "episodes", auto_sanitize=True)


def _clean_agy_env() -> dict[str, str]:
    """Use the user's normal Antigravity profile (avoid inheriting an isolated parent GEMINI_HOME)."""
    env = dict(os.environ)
    env.pop("GEMINI_HOME", None)
    return env


def extract_oauth_code(raw_input: str) -> str:
    """Accept either a raw Google OAuth code or a full callback URL containing ?code=..."""
    cleaned = raw_input.strip()
    if "code=" in cleaned:
        parsed = urllib.parse.urlparse(cleaned)
        qs = urllib.parse.parse_qs(parsed.query)
        if qs.get("code"):
            return qs["code"][0].strip()
        m = re.search(r"[?&]code=([^&\s]+)", cleaned)
        if m:
            return urllib.parse.unquote(m.group(1)).strip()
    return cleaned


def check_antigravity_auth(timeout_s: int = 12) -> dict[str, object]:
    """Check whether `agy` CLI is installed and signed into Google Antigravity."""
    agy_bin = shutil.which("agy")
    if not agy_bin:
        return {
            "installed": False,
            "logged_in": False,
            "models": [],
            "message": "Antigravity CLI (`agy`) belum terpasang di komputer ini.",
        }
    try:
        proc = subprocess.run(
            [agy_bin, "models"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=_clean_agy_env(),
            check=False,
            **silent_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired:
        return {
            "installed": True,
            "logged_in": False,
            "models": [],
            "message": "Cek status Antigravity timeout. Coba klik tombol Login Google Antigravity.",
        }

    out = strip_ansi((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    low = out.lower()
    if proc.returncode == 0 and "sign in" not in low and "authentication required" not in low:
        models = [
            line.strip().split()[0]
            for line in out.splitlines()
            if line.strip() and not line.lower().startswith("fetching") and "gemini" in line.lower()
        ]
        return {
            "installed": True,
            "logged_in": True,
            "models": models,
            "message": "Google Antigravity (Gemini 4 Neon High) sudah terhubung dan siap dipakai!",
        }
    return {
        "installed": True,
        "logged_in": False,
        "models": [],
        "message": "Google Antigravity belum login. Klik 'Login Google Antigravity' untuk konfirmasi 1x.",
    }


class AntigravityAuthManager:
    """Manages official `agy` OAuth login flow directly from the Studio UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._status: Literal["idle", "waiting_code", "done", "error"] = "idle"
        self._auth_url: str | None = None
        self._message: str = ""
        self._logs: list[str] = []

    def _cleanup_proc_locked(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.poll() is None:
                    self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def get_state(self, *, refresh_auth: bool = True) -> dict[str, object]:
        with self._lock:
            status = self._status
            auth_url = self._auth_url
            message = self._message
            logs = list(self._logs[-10:])
        auth = check_antigravity_auth() if (refresh_auth and status != "waiting_code") else None
        logged_in = bool(auth["logged_in"]) if auth else (status == "done")
        if logged_in and status != "done":
            with self._lock:
                self._status = "done"
                self._auth_url = None
                self._message = str(auth["message"]) if auth else "Terhubung!"
            status = "done"
            auth_url = None
            message = self._message
        return {
            "installed": bool(auth["installed"]) if auth else bool(shutil.which("agy")),
            "logged_in": logged_in,
            "status": status,
            "auth_url": auth_url,
            "message": message or (str(auth["message"]) if auth else ""),
            "logs": logs,
        }

    def start_login(self, open_browser: bool = True) -> dict[str, object]:
        agy_bin = shutil.which("agy")
        if not agy_bin:
            raise RuntimeError("Antigravity CLI (`agy`) belum terpasang di komputer ini.")

        # Already signed in?
        auth = check_antigravity_auth()
        if auth["logged_in"]:
            with self._lock:
                self._cleanup_proc_locked()
                self._status = "done"
                self._auth_url = None
                self._message = str(auth["message"])
            return self.get_state(refresh_auth=False)

        with self._lock:
            self._cleanup_proc_locked()
            self._status = "waiting_code"
            self._auth_url = None
            self._logs = []
            self._message = "Menyiapkan halaman konfirmasi login Google..."

            proc = subprocess.Popen(
                [agy_bin, "--model", "gemini-4-neon", "--output-format", "text", "--print", "OK"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_clean_agy_env(),
                **silent_subprocess_kwargs(),
            )
            self._proc = proc

        url_found = threading.Event()

        def _reader() -> None:
            assert proc.stdout is not None
            try:
                for raw_line in proc.stdout:
                    line = strip_ansi(raw_line).strip()
                    if not line:
                        continue
                    with self._lock:
                        self._logs.append(line)
                        m = re.search(r"(https://accounts\.google\.com/\S+)", line)
                        if m and not self._auth_url:
                            self._auth_url = m.group(1)
                            self._message = (
                                "Halaman login Google sudah dibuka! Klik Izinkan/Allow, "
                                "lalu tempel kode konfirmasi dari Google di bawah jika diminta."
                            )
                            url_found.set()
                rc = proc.wait()
                with self._lock:
                    if self._proc is proc:
                        self._proc = None
                    if rc == 0:
                        self._status = "done"
                        self._auth_url = None
                        self._message = "Berhasil login Google Antigravity (Gemini 4 Neon High)!"
                    elif self._status == "waiting_code":
                        self._status = "error"
                        self._message = "Sesi login berakhir/timeout (60 detik). Klik Login lagi untuk mengulang."
            except Exception as exc:
                with self._lock:
                    if self._status == "waiting_code":
                        self._status = "error"
                        self._message = f"Gagal membaca status login: {exc}"
            finally:
                url_found.set()

        threading.Thread(target=_reader, daemon=True).start()
        url_found.wait(timeout=12.0)

        with self._lock:
            url = self._auth_url
        if url and open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        return self.get_state(refresh_auth=False)

    def submit_code(self, raw_code: str) -> dict[str, object]:
        code = extract_oauth_code(raw_code)
        if not code:
            raise ValueError("Kode konfirmasi masih kosong.")

        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is not None or proc.stdin is None:
                raise RuntimeError(
                    "Sesi login sudah berakhir atau timeout (60 detik). Klik 'Login Google Antigravity' lagi."
                )
            try:
                proc.stdin.write(code + "\n")
                proc.stdin.flush()
            except Exception as exc:
                raise RuntimeError(f"Gagal mengirim kode ke Antigravity CLI: {exc}") from exc

        # Wait up to 20s for agy to complete login & exit 0
        deadline = time.time() + 20.0
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.35)

        auth = check_antigravity_auth()
        if auth["logged_in"]:
            with self._lock:
                self._cleanup_proc_locked()
                self._status = "done"
                self._auth_url = None
                self._message = "Login berhasil! Google Antigravity (Gemini 4 Neon High) sekarang siap dipakai."
            return self.get_state(refresh_auth=False)

        with self._lock:
            tail = " | ".join(self._logs[-3:])
        raise RuntimeError(
            f"Konfirmasi kode belum berhasil ({tail or 'kode mungkin sudah kedaluwarsa'}). "
            "Coba klik 'Login Google Antigravity' lagi dan gunakan kode terbaru."
        )


def build_antigravity_cmd(
    agy_bin: str,
    prompt: str,
    model: str = "gemini-4-neon",
    effort: str = "high",
) -> list[str]:
    """Build valid `agy` CLI args (`--print` consumes the prompt argument directly)."""
    return [
        agy_bin,
        "--model",
        model.strip() or "gemini-4-neon",
        "--effort",
        effort,
        "--disable-slash-commands",
        "--output-format",
        "text",
        "--print",
        prompt,
    ]


def _invoke_antigravity_once(
    agy_bin: str,
    project_root: Path,
    prompt: str,
    model: str,
    effort: str,
    timeout_s: int,
) -> str:
    cmd = build_antigravity_cmd(agy_bin, prompt, model=model, effort=effort)
    proc = subprocess.run(
        cmd,
        cwd=str(project_root),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        env=_clean_agy_env(),
        check=False,
        **silent_subprocess_kwargs(),
    )
    if proc.returncode != 0:
        err = strip_ansi(proc.stderr or proc.stdout).strip()[-1000:]
        low = err.lower()
        if "authentication" in low or "sign in" in low or "oauth" in low:
            raise RuntimeError(
                "ANTIGRAVITY_LOGIN_REQUIRED: Google Antigravity belum login. "
                "Klik tombol 'Login Google Antigravity Sekarang' di atas untuk konfirmasi login 1x."
            )
        raise RuntimeError(f"Antigravity CLI gagal (exit {proc.returncode}):\n{err}")
    return proc.stdout


def generate_script_via_antigravity(
    project_root: Path,
    prompt: str,
    model: str = "gemini-4-neon",
    effort: str = "high",
    timeout_s: int = 180,
    log_callback=None,
) -> dict[str, object]:
    agy_bin = shutil.which("agy")
    if not agy_bin:
        raise RuntimeError(
            "Antigravity CLI (`agy`) tidak ditemukan. Gunakan pilihan 'Kilo AI Gratis' di Pengaturan Lanjutan."
        )

    effective_model = model.strip() or "gemini-4-neon"
    raw_output = _invoke_antigravity_once(agy_bin, project_root, prompt, effective_model, effort, timeout_s)
    try:
        return validate_and_save_yaml(raw_output, project_root / "episodes", auto_sanitize=True)
    except Exception as first_err:
        if log_callback:
            log_callback("      Format YAML perlu dirapikan otomatis, mencoba perbaikan cepat (1/1)...")
        repair_prompt = (
            "Perbaiki YAML di bawah ini agar 100% valid mengikuti schema EpisodeSpec dan kembalikan "
            "HANYA 1 blok ```yaml ... ``` tanpa teks tambahan.\n\n"
            f"Error validasi:\n{first_err}\n\n"
            f"YAML sebelumnya:\n{strip_ansi(raw_output)[-4500:]}"
        )
        repaired_output = _invoke_antigravity_once(
            agy_bin, project_root, repair_prompt, effective_model, effort, timeout_s
        )
        return validate_and_save_yaml(repaired_output, project_root / "episodes", auto_sanitize=True)
