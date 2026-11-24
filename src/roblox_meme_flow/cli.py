from __future__ import annotations

import argparse
import json
import shutil
import socket
import sys
from pathlib import Path

from roblox_meme_flow.audio_video import assemble_video, find_ffmpeg, generate_voiceover_and_srt
from roblox_meme_flow.flow_runner import find_gflow_executable, write_and_optionally_run_flow
from roblox_meme_flow.layout import EpisodeLayout
from roblox_meme_flow.models import load_episode
from roblox_meme_flow.prompt_builder import export_plan
from roblox_meme_flow.validator import has_errors, validate_episode


def _check_cdp_port(port: int = 9222) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def cmd_doctor(_args: argparse.Namespace) -> int:
    try:
        import edge_tts  # noqa: F401

        edge_tts_ok = True
    except Exception:
        edge_tts_ok = False

    report = {
        "python": sys.version.split()[0],
        "gflow": find_gflow_executable(),
        "ffmpeg": find_ffmpeg(),
        "edge_tts": edge_tts_ok,
        "kilo_cli": shutil.which("kilo") or shutil.which("kilocode"),
        "chrome_cdp_9222_open": _check_cdp_port(9222),
    }
    print(json.dumps(report, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ep = load_episode(Path(args.episode))
    issues = validate_episode(ep)
    if not issues:
        print(f"OK: {ep.episode_id} passed all continuity and format checks ({ep.total_duration_seconds}s).")
        return 0
    for issue in issues:
        print(f"[{issue.severity.upper()}] {issue.code}: {issue.message}")
    return 1 if has_errors(issues) else 0


def cmd_plan(args: argparse.Namespace) -> int:
    ep_path = Path(args.episode)
    ep = load_episode(ep_path)
    issues = validate_episode(ep)
    for issue in issues:
        print(f"[{issue.severity.upper()}] {issue.code}: {issue.message}")
    if has_errors(issues):
        print("Aborting plan export due to validation errors.")
        return 1
    ep_dir = export_plan(ep, Path(args.out_dir), source_yaml=ep_path)
    print(f"Exported production plan to: {ep_dir}")
    return 0


def cmd_run_flow(args: argparse.Namespace) -> int:
    ep = load_episode(Path(args.episode))
    issues = validate_episode(ep)
    if has_errors(issues):
        for issue in issues:
            print(f"[{issue.severity.upper()}] {issue.code}: {issue.message}")
        return 1
    stage_map: dict[str, set[str] | None] = {
        "all": None,
        "images": {"reference_image", "storyboard"},
        "video": {"video_scene"},
    }
    try:
        manifest_path = write_and_optionally_run_flow(
            ep=ep,
            out_dir=Path(args.out_dir),
            spend=bool(args.spend),
            execute=bool(args.execute),
            stages=stage_map[args.stage],
            override_limit=bool(args.override_limit),
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    mode = "LIVE SPEND" if args.spend else "DRY-RUN (--max-credits 0)"
    print(f"[{mode}] Manifest written to: {manifest_path}")
    return 0


def cmd_research(args: argparse.Namespace) -> int:
    from roblox_meme_flow.script_gen import build_t3_generation_prompt

    prompt, brief = build_t3_generation_prompt(
        project_root=Path.cwd(),
        content_mode=args.mode,
        budget_preset=args.budget,
        topic_hint=args.topic or "",
    )
    print(brief.to_prompt_block())
    print("\n" + "=" * 60 + "\n")
    print(prompt)
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    import uvicorn

    from roblox_meme_flow.web_ui import create_app

    app = create_app(Path.cwd())
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_voiceover(args: argparse.Namespace) -> int:
    ep = load_episode(Path(args.episode))
    mp3_path, srt_path = generate_voiceover_and_srt(ep, Path(args.out_dir))
    print(f"Voiceover: {mp3_path}")
    print(f"Captions : {srt_path}")
    return 0


def cmd_assemble(args: argparse.Namespace) -> int:
    ep = load_episode(Path(args.episode))
    clips = [Path(c) for c in args.clips]
    out_dir = Path(args.out_dir)
    layout = EpisodeLayout.for_episode(out_dir, ep.episode_id)
    vo = Path(args.voiceover) if args.voiceover else (layout.audio_dir / "voiceover.mp3")
    srt = Path(args.srt) if args.srt else (layout.subtitles_dir / "captions.srt")
    output_mp4 = assemble_video(
        ep=ep,
        clips=clips,
        out_dir=out_dir,
        voiceover_path=vo if vo.exists() else None,
        srt_path=srt if srt.exists() else None,
    )
    print(f"Assembled final video: {output_mp4}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rmf",
        description="Roblox-Meme-Flow: Daily Indonesian 'Di Dunia Ini' Google Flow video pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Check local tooling and Chrome CDP readiness.")
    p_doc.set_defaults(func=cmd_doctor)

    p_val = sub.add_parser("validate", help="Validate an episode YAML spec.")
    p_val.add_argument("episode", help="Path to episode YAML file.")
    p_val.set_defaults(func=cmd_validate)

    p_plan = sub.add_parser("plan", help="Export reference, storyboard, scene prompts, and SRT.")
    p_plan.add_argument("episode", help="Path to episode YAML file.")
    p_plan.add_argument("--out-dir", default="outputs", help="Output root directory.")
    p_plan.set_defaults(func=cmd_plan)

    p_flow = sub.add_parser("run-flow", help="Generate gflow-cli manifest and optionally execute.")
    p_flow.add_argument("episode", help="Path to episode YAML file.")
    p_flow.add_argument("--out-dir", default="outputs", help="Output root directory.")
    p_flow.add_argument(
        "--spend",
        action="store_true",
        help="Explicitly allow spending Google Flow video credits (default enforces --max-credits 0).",
    )
    p_flow.add_argument(
        "--stage",
        choices=["all", "images", "video"],
        default="all",
        help="Which stage(s) to run when --execute is set (default: all).",
    )
    p_flow.add_argument(
        "--execute",
        action="store_true",
        help="Actually invoke local gflow CLI instead of manifest-only.",
    )
    p_flow.add_argument(
        "--override-limit",
        action="store_true",
        help="Override the daily 50-credit / 1-video limit.",
    )
    p_flow.set_defaults(func=cmd_run_flow)

    p_res = sub.add_parser("research", help="Run live viral trend research and print T3 script prompt.")
    p_res.add_argument("--mode", choices=["meme_roblox_id", "kids_animation_id"], default="meme_roblox_id")
    p_res.add_argument("--budget", default="hemat_50")
    p_res.add_argument("--topic", default="")
    p_res.set_defaults(func=cmd_research)

    p_ui = sub.add_parser("ui", help="Launch the local Roblox-Meme-Flow Studio Web UI.")
    p_ui.add_argument("--host", default="127.0.0.1")
    p_ui.add_argument("--port", type=int, default=8787)
    p_ui.set_defaults(func=cmd_ui)

    p_vo = sub.add_parser("voiceover", help="Synthesize Indonesian voiceover MP3 and SRT captions.")
    p_vo.add_argument("episode", help="Path to episode YAML file.")
    p_vo.add_argument("--out-dir", default="outputs", help="Output root directory.")
    p_vo.set_defaults(func=cmd_voiceover)

    p_asm = sub.add_parser("assemble", help="Stitch clips + VO + subtitles into final 9:16 MP4.")
    p_asm.add_argument("episode", help="Path to episode YAML file.")
    p_asm.add_argument("--clips", nargs="+", required=True, help="Ordered MP4 clip paths.")
    p_asm.add_argument("--voiceover", default=None, help="Optional path to voiceover MP3.")
    p_asm.add_argument("--srt", default=None, help="Optional path to SRT captions.")
    p_asm.add_argument("--out-dir", default="outputs", help="Output root directory.")
    p_asm.set_defaults(func=cmd_assemble)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
