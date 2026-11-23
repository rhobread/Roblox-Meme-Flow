from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from roblox_meme_flow.models import EpisodeSpec
from roblox_meme_flow.prompt_builder import (
    build_reference_prompts,
    build_scene_video_prompts,
    build_storyboard_prompt,
)


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

    commands: list[dict[str, object]] = []
    ref_files: dict[str, Path] = {}

    for handle, prompt in refs.items():
        safe_name = handle.lstrip("@")
        out_file = ep_dir / "refs" / f"{safe_name}.png"
        ref_files[handle] = out_file
        commands.append(
            {
                "stage": "reference_image",
                "target": handle,
                "output_hint": str(out_file),
                "prompt": prompt,
                "args": [
                    gflow_bin,
                    "image",
                    "t2i",
                    prompt,
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

    storyboard_out = ep_dir / "storyboard.png"
    commands.append(
        {
            "stage": "storyboard",
            "target": "storyboard",
            "output_hint": str(storyboard_out),
            "prompt": storyboard,
            "args": [
                gflow_bin,
                "image",
                "t2i",
                storyboard,
                "--model",
                ep.image_model,
                "--aspect",
                ep.aspect_ratio,
                "--out-file",
                str(storyboard_out),
                "--json",
            ],
        }
    )

    for scene in scenes:
        clip_out = ep_dir / "clips" / f"scene_{scene['scene_number']:02d}.mp4"
        args = [
            gflow_bin,
            "video",
            "gen",
            str(scene["prompt"]),
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
                "prompt": scene["prompt"],
                "args": args,
            }
        )

    return {
        "episode_id": ep.episode_id,
        "spend_enabled": spend,
        "gflow_executable": gflow_bin,
        "commands": commands,
    }


def write_and_optionally_run_flow(
    ep: EpisodeSpec,
    out_dir: Path,
    spend: bool = False,
    execute: bool = False,
    stages: set[str] | None = None,
) -> Path:
    ep_dir = out_dir / ep.episode_id
    (ep_dir / "refs").mkdir(parents=True, exist_ok=True)
    (ep_dir / "clips").mkdir(parents=True, exist_ok=True)

    manifest = build_gflow_manifest(ep, ep_dir, spend=spend)
    manifest_path = ep_dir / "gflow_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    if not execute:
        return manifest_path

    gflow_bin = find_gflow_executable()
    if not gflow_bin:
        raise RuntimeError(
            "gflow executable not found. Install dependencies inside .venv with `pip install -e .`."
        )

    results = []
    for step in manifest["commands"]:  # type: ignore[index]
        if stages and step["stage"] not in stages:
            continue
        proc = subprocess.run(
            step["args"],
            capture_output=True,
            text=True,
            check=False,
        )
        results.append(
            {
                "stage": step["stage"],
                "target": step["target"],
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-2000:],
            }
        )
        if proc.returncode != 0:
            break

    (ep_dir / "gflow_run_log.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest_path
