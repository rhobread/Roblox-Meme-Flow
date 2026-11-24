from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from roblox_meme_flow.credit_guard import (
    check_render_budget,
    estimate_episode_credits,
    record_render_spend,
)
from roblox_meme_flow.layout import EpisodeLayout
from roblox_meme_flow.models import EpisodeSpec
from roblox_meme_flow.prompt_builder import (
    build_reference_prompts,
    build_scene_video_prompts,
    build_storyboard_prompt,
)
from roblox_meme_flow.win_silent import (
    run_silent_gflow_subprocess,
    silent_subprocess_kwargs,
)

AT_HANDLE_RE = re.compile(r"@([A-Z][A-Za-z0-9]*)")
_GFLOW_PROFILE_LOCK = threading.Lock()


def strip_at_handles_for_gflow(prompt: str) -> str:
    """Strip '@' from @PascalCase handles before sending to gflow CLI.

    gflow-cli interprets inline '@Name' as a saved Google Flow Character entity picker
    lookup and aborts with exit 32 when no pre-saved character entity exists. When using
    local --ref PNG files, plain names keep continuity while avoiding picker lookup errors.
    """
    return AT_HANDLE_RE.sub(r"\1", prompt)


def find_gflow_executable() -> str | None:
    venv_gflow = Path(sys.executable).parent / "gflow.exe"
    if venv_gflow.exists():
        return str(venv_gflow)
    return shutil.which("gflow")


def build_gflow_manifest(
    ep: EpisodeSpec,
    ep_dir: Path,
    spend: bool = False,
    max_credits_per_clip: int | None = None,
) -> dict[str, object]:
    """Build exact gflow-cli (v0.105+) commands with --max-credits 0 protection by default."""
    gflow_bin = find_gflow_executable() or "gflow"
    refs = build_reference_prompts(ep)
    storyboard = build_storyboard_prompt(ep)
    scenes = build_scene_video_prompts(ep)

    layout = EpisodeLayout.for_episode(ep_dir.parent, ep_dir.name)
    commands: list[dict[str, object]] = []
    ref_files: dict[str, Path] = {}

    for handle, prompt in refs.items():
        safe_name = handle.lstrip("@")
        out_file = layout.refs_dir / f"{safe_name}.jpg"
        ref_files[handle] = out_file
        wire_prompt = strip_at_handles_for_gflow(prompt)
        commands.append(
            {
                "stage": "reference_image",
                "target": handle,
                "output_hint": str(out_file),
                "prompt": wire_prompt,
                "args": [
                    gflow_bin,
                    "image",
                    "t2i",
                    wire_prompt,
                    "--model",
                    ep.image_model,
                    "--aspect",
                    ep.aspect_ratio,
                    "--out-file",
                    str(out_file),
                    "--json",
                ],
            }
        )

    storyboard_out = layout.images_dir / "storyboard.jpg"
    wire_storyboard = strip_at_handles_for_gflow(storyboard)
    storyboard_args = [
        gflow_bin,
        "image",
        "gen",
        wire_storyboard,
        "--model",
        ep.image_model,
        "--aspect",
        ep.aspect_ratio,
        "--out-file",
        str(storyboard_out),
        "--json",
    ]
    for ref_path in list(ref_files.values())[:4]:
        storyboard_args.extend(["--ref", str(ref_path)])

    commands.append(
        {
            "stage": "storyboard",
            "target": "storyboard",
            "output_hint": str(storyboard_out),
            "prompt": wire_storyboard,
            "args": storyboard_args,
        }
    )

    is_veo_model = ep.video_model.strip().lower().startswith("veo-")
    model_ref_cap = 3 if is_veo_model else 7
    for scene in scenes:
        clip_out = layout.clips_dir / f"scene_{scene['scene_number']:02d}.mp4"
        wire_scene = strip_at_handles_for_gflow(str(scene["prompt"]))
        ref_args: list[str] = []
        added_refs = 0
        for ref_handle in scene["references"]:  # type: ignore[union-attr]
            if ref_handle in ref_files and added_refs < model_ref_cap:
                ref_args.extend(["--ref", str(ref_files[ref_handle])])
                added_refs += 1

        args = [
            gflow_bin,
            "video",
            "gen",
            wire_scene,
            "--model",
            ep.video_model,
            "--aspect",
            ep.aspect_ratio,
        ]
        # Google Flow pins Veo R2V (--ref) clips to 8s and rejects --duration 4/6 with exit 11.
        # Omit --duration on Veo R2V so gflow pins 8s cleanly (flat 10 cr on veo-lite; fast_cut_sync trims to VO).
        if not (is_veo_model and added_refs > 0):
            args.extend(["--duration", str(scene["duration_seconds"])])

        args.extend(
            [
                "--out-file",
                str(clip_out),
                "--json",
                *ref_args,
            ]
        )

        if not spend:
            args.extend(["--max-credits", "0"])
        elif max_credits_per_clip is not None:
            args.extend(["--max-credits", str(max_credits_per_clip)])

        commands.append(
            {
                "stage": "video_scene",
                "target": f"scene_{scene['scene_number']}",
                "output_hint": str(clip_out),
                "prompt": wire_scene,
                "args": args,
            }
        )

    return {
        "episode_id": ep.episode_id,
        "spend_enabled": spend,
        "gflow_executable": gflow_bin,
        "commands": commands,
    }


def _resolve_existing_media(path: Path) -> Path | None:
    if path.exists():
        return path
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        cand = path.with_suffix(ext)
        if cand.exists():
            return cand
    return None


def _resolve_ref_args(args: list[str]) -> list[str]:
    resolved = list(args)
    for idx, token in enumerate(resolved):
        if token == "--ref" and idx + 1 < len(resolved):
            found = _resolve_existing_media(Path(resolved[idx + 1]))
            if found is not None:
                resolved[idx + 1] = str(found)
    return resolved


def _silent_gflow_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("GFLOW_CLI_BROWSER_WINDOW_POSITION", "-30000,-30000")
    env.setdefault("GFLOW_CLI_LEASE_WAIT_SECONDS", "45")
    return env


def get_live_flow_credits() -> int | None:
    """Read live Google Flow credit balance via `gflow credits user` (0 credits spent)."""
    gflow_bin = find_gflow_executable()
    if not gflow_bin:
        return None
    if not _GFLOW_PROFILE_LOCK.acquire(timeout=2.0):
        return None
    try:
        proc = subprocess.run(
            [gflow_bin, "credits", "user"],
            capture_output=True,
            text=True,
            timeout=30,
            env=_silent_gflow_env(),
            check=False,
            **silent_subprocess_kwargs(),
        )
    finally:
        _GFLOW_PROFILE_LOCK.release()
    if proc.returncode != 0:
        return None
    match = re.search(r"Credits:\s*(\d+)", proc.stdout)
    if match:
        return int(match.group(1))
    return None


STAGE_TIMEOUTS_SECONDS: dict[str, float] = {
    "reference_image": 150.0,
    "storyboard": 180.0,
    "video_scene": 240.0,
}


def write_and_optionally_run_flow(
    ep: EpisodeSpec,
    out_dir: Path,
    spend: bool = False,
    execute: bool = False,
    stages: set[str] | None = None,
    override_limit: bool = False,
    log_callback=None,
    optional_stages: set[str] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    def _emit(msg: str) -> None:
        print(msg, flush=True)
        if log_callback:
            log_callback(msg)

    layout = EpisodeLayout.for_episode(out_dir, ep.episode_id)
    layout.ensure_dirs()
    ledger_path = out_dir / "credit_ledger.json"

    will_run_video = execute and spend and (stages is None or "video_scene" in stages)
    credits_before: int | None = None
    per_clip_cap: int | None = None

    if will_run_video:
        credits_before = get_live_flow_credits()
        budget = check_render_budget(
            ep=ep,
            ledger_path=ledger_path,
            live_balance=credits_before,
            override_limit=override_limit,
        )
        per_clip_cap = budget.per_clip_max_credits
        _emit(f"[BUDGET] {budget.reason}")
        if not budget.allowed:
            raise RuntimeError(budget.reason)

    manifest = build_gflow_manifest(
        ep,
        layout.root,
        spend=spend,
        max_credits_per_clip=per_clip_cap,
    )
    manifest_path = layout.logs_dir / "gflow_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    if not execute:
        return manifest_path

    gflow_bin = find_gflow_executable()
    if not gflow_bin:
        raise RuntimeError(
            "gflow executable not found. Install dependencies inside .venv with `pip install -e .`."
        )

    opt_stages = optional_stages or set()
    selected_steps = [
        step for step in manifest["commands"] if not stages or step["stage"] in stages  # type: ignore[index]
    ]
    total_steps = len(selected_steps)

    results = []
    failed_step: dict[str, object] | None = None
    for idx, step in enumerate(selected_steps, start=1):
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError("Proses dibatalkan oleh pengguna.")

        stage = str(step["stage"])
        target = str(step["target"])
        out_hint = Path(str(step["output_hint"]))

        # Skip existing valid references AND existing valid rendered clips (never double-spend credits!)
        if stage == "reference_image":
            existing = _resolve_existing_media(out_hint)
            if existing is not None and existing.stat().st_size > 1000:
                _emit(f"-> ({idx}/{total_steps}) Sudah ada [{stage}] {target} ({existing.name}) - dilewati")
                results.append(
                    {
                        "stage": stage,
                        "target": target,
                        "returncode": 0,
                        "skipped": True,
                        "existing_file": str(existing),
                    }
                )
                continue
        elif stage == "video_scene" and out_hint.exists() and out_hint.stat().st_size > 10_000:
            _emit(f"-> ({idx}/{total_steps}) Klip sudah ada [{stage}] {target} ({out_hint.name}) - hemat kredit!")
            results.append(
                {
                    "stage": stage,
                    "target": target,
                    "returncode": 0,
                    "skipped": True,
                    "existing_file": str(out_hint),
                }
            )
            continue

        run_args = _resolve_ref_args([str(a) for a in step["args"]])
        step_timeout = STAGE_TIMEOUTS_SECONDS.get(stage, 180.0)
        _emit(f"-> ({idx}/{total_steps}) Menjalankan [{stage}] {target} (maks {int(step_timeout)} detik)...")
        try:
            with _GFLOW_PROFILE_LOCK:
                proc = run_silent_gflow_subprocess(
                    run_args,
                    env=_silent_gflow_env(),
                    timeout=step_timeout,
                )
            record = {
                "stage": stage,
                "target": target,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-2000:],
            }
        except subprocess.TimeoutExpired:
            record = {
                "stage": stage,
                "target": target,
                "returncode": 124,
                "stdout": "",
                "stderr": f"Timeout setelah {int(step_timeout)} detik menunggu respons Google Flow.",
            }

        results.append(record)
        if record["returncode"] != 0:
            if stage in opt_stages:
                _emit(
                    f"[INFO] Tahap opsional [{stage}] melewati batas waktu / gagal — "
                    "tetapi gambar referensi & suara narator sudah siap dipakai."
                )
                continue
            failed_step = record
            break

    log_path = layout.logs_dir / "gflow_run_log.json"
    log_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    if will_run_video:
        credits_after = get_live_flow_credits()
        if credits_before is not None and credits_after is not None and credits_before >= credits_after:
            spent = credits_before - credits_after
        else:
            spent = estimate_episode_credits(ep) if failed_step is None else 0
        if spent > 0:
            record_render_spend(ledger_path, ep.episode_id, spent)
            _emit(f"[BUDGET] Tercatat terpakai {spent} kredit hari ini (saldo: {credits_after}).")

    if failed_step is not None:
        detail = (str(failed_step.get("stderr") or "") or str(failed_step.get("stdout") or "")).strip()[-400:]
        raise RuntimeError(
            f"Google Flow gagal di tahap [{failed_step['stage']}] {failed_step['target']} "
            f"(exit {failed_step['returncode']}). {detail}\nLog lengkap: {log_path}"
        )

    return manifest_path
