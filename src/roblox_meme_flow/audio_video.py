from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from roblox_meme_flow.layout import EpisodeLayout
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


def _probe_duration_seconds(ffmpeg: str, media_path: Path) -> float | None:
    proc = subprocess.run(
        [ffmpeg, "-i", str(media_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            part = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
            hms = part.split(":")
            if len(hms) == 3:
                try:
                    return int(hms[0]) * 3600 + int(hms[1]) * 60 + float(hms[2])
                except ValueError:
                    return None
    return None


def _has_audio_stream(ffmpeg: str, media_path: Path) -> bool:
    proc = subprocess.run(
        [ffmpeg, "-i", str(media_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return "Audio:" in proc.stderr


async def _synthesize_edge_tts(
    text: str, voice: str, rate: str, pitch: str, out_mp3: Path
) -> None:
    import edge_tts

    communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicator.save(str(out_mp3))


def _fit_scene_audio(
    ffmpeg: str,
    raw_mp3: Path,
    target_seconds: float,
    out_wav: Path,
    pitch_shift: float = 1.0,
) -> None:
    """Fit a scene voiceover cleanly into target_seconds with optional comedic pitch shift."""
    actual = _probe_duration_seconds(ffmpeg, raw_mp3)
    filters: list[str] = []

    # Apply natural cartoon/meme pitch shift while preserving speaking duration
    tempo_comp = 1.0
    if abs(pitch_shift - 1.0) > 0.005:
        shifted_rate = int(round(44100 * pitch_shift))
        filters.append("aresample=44100")
        filters.append(f"asetrate={shifted_rate}")
        filters.append("aresample=44100")
        tempo_comp = 1.0 / pitch_shift

    if actual and actual > target_seconds - 0.15:
        tempo_comp *= actual / max(target_seconds - 0.15, 1.0)

    # ffmpeg atempo supports [0.5, 2.0] per stage
    if abs(tempo_comp - 1.0) > 0.005:
        clamped = max(0.5, min(tempo_comp, 2.0))
        filters.append(f"atempo={clamped:.3f}")

    # Crisp comedic vocal presence for mobile Shorts/TikTok speakers
    filters.append("highpass=f=120")
    filters.append("acompressor=threshold=-16dB:ratio=3:attack=5:release=60")
    filters.append("apad")
    filters.append(f"atrim=0:{target_seconds:.3f}")

    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(raw_mp3),
            "-af",
            ",".join(filters),
            "-ar",
            "44100",
            "-ac",
            "2",
            str(out_wav),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed fitting scene audio: {proc.stderr[-1000:]}")


def generate_voiceover_and_srt(ep: EpisodeSpec, out_dir: Path) -> tuple[Path, Path]:
    layout = EpisodeLayout.for_episode(out_dir, ep.episode_id)
    layout.ensure_dirs()

    vo_dir = layout.vo_scenes_dir
    mp3_path = layout.audio_dir / "voiceover.mp3"
    srt_path = layout.subtitles_dir / "captions.srt"
    srt_path.write_text(build_srt(ep), encoding="utf-8")

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        full_narration = " ".join(scene.narration_id.strip() for scene in ep.scenes)
        asyncio.run(
            _synthesize_edge_tts(full_narration, ep.tts_voice, ep.tts_rate, ep.tts_pitch, mp3_path)
        )
        return mp3_path, srt_path

    fitted_wavs: list[Path] = []
    for scene in ep.scenes:
        raw_scene_mp3 = vo_dir / f"scene_{scene.scene_number:02d}_raw.mp3"
        fitted_wav = vo_dir / f"scene_{scene.scene_number:02d}_fit.wav"
        asyncio.run(
            _synthesize_edge_tts(
                scene.narration_id.strip(),
                ep.tts_voice,
                ep.tts_rate,
                ep.tts_pitch,
                raw_scene_mp3,
            )
        )
        _fit_scene_audio(
            ffmpeg,
            raw_scene_mp3,
            float(scene.duration_seconds),
            fitted_wav,
            pitch_shift=ep.tts_pitch_shift,
        )
        fitted_wavs.append(fitted_wav)

    concat_txt = vo_dir / "vo_concat.txt"
    concat_txt.write_text(
        "\n".join(f"file '{w.resolve().as_posix()}'" for w in fitted_wavs) + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(mp3_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed concatenating voiceover: {proc.stderr[-1000:]}")

    return mp3_path, srt_path


def _escape_ffmpeg_filter_path(path: Path) -> str:
    raw = path.resolve().as_posix()
    return raw.replace(":", r"\:").replace("'", r"\'")


def assemble_video(
    ep: EpisodeSpec,
    clips: list[Path],
    out_dir: Path,
    voiceover_path: Path | None = None,
    srt_path: Path | None = None,
    bgm_path: Path | None = None,
) -> Path:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("No ffmpeg binary found (install ffmpeg or imageio-ffmpeg).")
    if not clips:
        raise ValueError("At least one video clip is required to assemble the final video.")

    layout = EpisodeLayout.for_episode(out_dir, ep.episode_id)
    layout.ensure_dirs()

    # Resolve BGM file if configured
    resolved_bgm: Path | None = None
    if bgm_path and bgm_path.exists():
        resolved_bgm = bgm_path
    elif ep.bgm_path:
        cand = Path(ep.bgm_path)
        if not cand.is_absolute():
            cand = Path.cwd() / cand
        if cand.exists():
            resolved_bgm = cand

    # Normalize each clip to uniform 1080x1920 30fps H.264/AAC first so concat never glitches
    norm_dir = layout.clips_norm_dir
    normalized_clips: list[Path] = []
    all_have_audio = True

    for idx, clip in enumerate(clips, start=1):
        norm_path = norm_dir / f"norm_{idx:02d}.mp4"
        clip_has_audio = _has_audio_stream(ffmpeg, clip)
        if not clip_has_audio:
            all_have_audio = False

        norm_cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(clip),
        ]
        if not clip_has_audio:
            norm_cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        norm_cmd.extend(
            [
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-b:a",
                "192k",
            ]
        )
        if not clip_has_audio:
            norm_cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-shortest"])
        norm_cmd.append(str(norm_path))

        proc = subprocess.run(norm_cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg normalize failed for {clip.name}: {proc.stderr[-1000:]}")
        normalized_clips.append(norm_path)

    concat_list = layout.logs_dir / "concat_clips.txt"
    lines = [f"file '{c.resolve().as_posix()}'" for c in normalized_clips]
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    output_mp4 = layout.final_dir / "final_9x16.mp4"

    vf_filters = ["fps=30"]
    if ep.enable_subtitles and srt_path and srt_path.exists():
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

    vo_idx: int | None = None
    bgm_idx: int | None = None
    next_idx = 1

    if voiceover_path and voiceover_path.exists():
        cmd.extend(["-i", str(voiceover_path)])
        vo_idx = next_idx
        next_idx += 1

    if resolved_bgm is not None and ep.bgm_volume > 0.0:
        cmd.extend(["-stream_loop", "-1", "-i", str(resolved_bgm)])
        bgm_idx = next_idx
        next_idx += 1

    fade_start = max(0.5, float(ep.total_duration_seconds) - 1.2)
    audio_parts: list[str] = []
    mix_labels: list[str] = []

    if all_have_audio:
        sfx_vol = 0.25 if vo_idx is not None else 0.85
        audio_parts.append(f"[0:a]volume={sfx_vol:.2f}[sfx]")
        mix_labels.append("[sfx]")

    if vo_idx is not None:
        audio_parts.append(f"[{vo_idx}:a]volume=1.00,apad[vo]")
        mix_labels.append("[vo]")

    if bgm_idx is not None:
        audio_parts.append(
            f"[{bgm_idx}:a]volume={ep.bgm_volume:.2f},"
            f"afade=t=in:st=0:d=0.4,"
            f"afade=t=out:st={fade_start:.2f}:d=1.2[bgm]"
        )
        mix_labels.append("[bgm]")

    if len(mix_labels) >= 2:
        filter_complex = (
            ";".join(audio_parts)
            + f";{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2:normalize=0[aout]"
        )
        cmd.extend(["-filter_complex", filter_complex, "-map", "0:v:0", "-map", "[aout]"])
    elif len(mix_labels) == 1:
        label = mix_labels[0]
        cmd.extend(["-filter_complex", audio_parts[0], "-map", "0:v:0", "-map", label])
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
            "-shortest",
            str(output_mp4),
        ]
    )

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg assemble failed ({proc.returncode}): {proc.stderr[-1500:]}")
    return output_mp4
