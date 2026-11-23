from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from roblox_meme_flow.models import EpisodeSpec
from roblox_meme_flow.prompt_builder import build_srt


def find_ffmpeg() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


async def _synthesize_edge_tts(text: str, voice: str, rate: str, out_mp3: Path) -> None:
    import edge_tts

    communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicator.save(str(out_mp3))


def generate_voiceover_and_srt(ep: EpisodeSpec, out_dir: Path) -> tuple[Path, Path]:
    ep_dir = out_dir / ep.episode_id
    ep_dir.mkdir(parents=True, exist_ok=True)

    full_narration = " ".join(scene.narration_id.strip() for scene in ep.scenes)
    mp3_path = ep_dir / "voiceover.mp3"
    srt_path = ep_dir / "captions.srt"

    srt_path.write_text(build_srt(ep), encoding="utf-8")
    asyncio.run(_synthesize_edge_tts(full_narration, ep.tts_voice, ep.tts_rate, mp3_path))
    return mp3_path, srt_path


def _escape_ffmpeg_filter_path(path: Path) -> str:
    # Escape Windows drive colon and backslashes for ffmpeg subtitles filter
    raw = path.resolve().as_posix()
    return raw.replace(":", r"\:").replace("'", r"\'")


def assemble_video(
    ep: EpisodeSpec,
    clips: list[Path],
    out_dir: Path,
    voiceover_path: Path | None = None,
    srt_path: Path | None = None,
) -> Path:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("No ffmpeg binary found (install ffmpeg or imageio-ffmpeg).")
    if not clips:
        raise ValueError("At least one video clip is required to assemble the final video.")

    ep_dir = out_dir / ep.episode_id
    ep_dir.mkdir(parents=True, exist_ok=True)

    concat_list = ep_dir / "concat_clips.txt"
    lines = [f"file '{clip.resolve().as_posix()}'" for clip in clips]
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    output_mp4 = ep_dir / "final_9x16.mp4"

    vf_filters = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        "fps=30",
    ]
    if srt_path and srt_path.exists():
        escaped = _escape_ffmpeg_filter_path(srt_path)
        style = (
            "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=85"
        )
        vf_filters.append(f"subtitles='{escaped}':force_style='{style}'")

    cmd: list[str] = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
    ]

    if voiceover_path and voiceover_path.exists():
        cmd.extend(["-i", str(voiceover_path)])
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-shortest"])
    else:
        cmd.extend(["-map", "0:v:0", "-map", "0:a?"])

    cmd.extend(
        [
            "-vf",
            ",".join(vf_filters),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_mp4),
        ]
    )

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-1500:]}")
    return output_mp4
