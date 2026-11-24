from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
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

AT_HANDLE_RE = re.compile(r"@([A-Z][A-Za-z0-9]*)")


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
    for ref_path in ref_files.values():
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

    for scene in scenes:
        clip_out = layout.clips_dir / f"scene_{scene['scene_number']:02d}.mp4"
        wire_scene = strip_at_handles_for_gflow(str(scene["prompt"]))
        args = [
            gflow_bin,
            "video",
            "gen",
            wire_scene,
            "--model",
            ep.video_model,
            "--aspect",
            ep.aspect_ratio,
            "--duration",
            str(scene["duration_seconds"]),
            "--out-file",
            str(clip_out),
            "--json",
        ]
        for ref_handle in scene["references"]:  # type: ignore[union-attr]
            if ref_handle in ref_files:
                args.extend(["--ref", str(ref_files[ref_handle])])

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


def get_live_flow_credits() -> int | None:
    """Read live Google Flow credit balance via `gflow credits user` (0 credits spent)."""
    gflow_bin = find_gflow_executable()
    if not gflow_bin:
        return None
    proc = subprocess.run(
        [gflow_bin, "credits", "user"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        return None
    match = re.search(r"Credits:\s*(\d+)", proc.stdout)
    if match:
        return int(match.group(1))
    return None


def write_and_optionally_run_flow(
    ep: EpisodeSpec,
    out_dir: Path,
    spend: bool = False,
    execute: bool = False,
    stages: set[str] | None = None,
    override_limit: bool = False,
    log_callback=None,
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

    results = []
    failed_step: dict[str, object] | None = None
    for step in manifest["commands"]:  # type: ignore[index]
        if stages and step["stage"] not in stages:
            continue
        existing = _resolve_existing_media(Path(str(step["output_hint"])))
        if existing is not None and step["stage"] == "reference_image":
            _emit(f"-> Skipping existing [{step['stage']}] {step['target']} ({existing.name})")
            results.append(
                {
                    "stage": step["stage"],
                    "target": step["target"],
                    "returncode": 0,
                    "skipped": True,
                    "existing_file": str(existing),
                }
            )
            continue

        run_args = _resolve_ref_args([str(a) for a in step["args"]])
        _emit(f"-> Running [{step['stage']}] {step['target']}...")
        proc = subprocess.run(
            run_args,
            capture_output=True,
            text=True,
            check=False,
        )
        record = {
            "stage": step["stage"],
            "target": step["target"],
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-2000:],
        }
        results.append(record)
        if proc.returncode != 0:
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
        raise RuntimeError(
            f"gflow failed at [{failed_step['stage']}] {failed_step['target']} "
            f"(exit {failed_step['returncode']}). See {log_path}"
        )

    return manifest_path
