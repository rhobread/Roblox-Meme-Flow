from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from roblox_meme_flow.layout import EpisodeLayout
from roblox_meme_flow.models import EpisodeSpec
from roblox_meme_flow.prompt_builder import build_srt
from roblox_meme_flow.win_silent import silent_subprocess_kwargs


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
        **silent_subprocess_kwargs(),
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
        **silent_subprocess_kwargs(),
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
    max_seconds: float,
    out_wav: Path,
    pitch_shift: float = 1.0,
    fast_cut_sync: bool = True,
    gap_seconds: float = 0.10,
) -> float:
    """Process scene VO: strip dead pauses, apply meme pitch shift, return exact final duration."""
    # Pass 1: apply comedic pitch shift + vocal pop + trim dead silences (>0.12s)
    trimmed_wav = out_wav.with_name(out_wav.stem + "_trim.wav")
    pre_filters: list[str] = []
    if abs(pitch_shift - 1.0) > 0.005:
        shifted_rate = int(round(44100 * pitch_shift))
        pre_filters.append("aresample=44100")
        pre_filters.append(f"asetrate={shifted_rate}")
        pre_filters.append("aresample=44100")
        pre_filters.append(f"atempo={max(0.5, min(1.0 / pitch_shift, 2.0)):.3f}")

    pre_filters.append("highpass=f=120")
    pre_filters.append("acompressor=threshold=-16dB:ratio=3:attack=5:release=60")
    # Strip leading silence and tighten long internal/trailing pauses so narration flows nonstop
    pre_filters.append(
        "silenceremove=start_periods=1:start_duration=0:start_threshold=-42dB:"
        "stop_periods=-1:stop_duration=0.12:stop_threshold=-42dB"
    )

    proc1 = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(raw_mp3),
            "-af",
            ",".join(pre_filters),
            "-ar",
            "44100",
            "-ac",
            "2",
            str(trimmed_wav),
        ],
        capture_output=True,
        text=True,
        check=False,
        **silent_subprocess_kwargs(),
    )
    if proc1.returncode != 0:
        raise RuntimeError(f"ffmpeg failed trimming scene audio: {proc1.stderr[-1000:]}")

    spoken_s = _probe_duration_seconds(ffmpeg, trimmed_wav) or max_seconds

    # Pass 2: if fast_cut_sync is enabled, cut tightly to spoken_s + tiny breath gap (<= max_seconds)
    # so there are ZERO awkward silent pauses between scenes.
    post_filters: list[str] = []
    if spoken_s > max_seconds - 0.08:
        speed = min(spoken_s / max(max_seconds - 0.08, 0.8), 1.65)
        post_filters.append(f"atempo={speed:.3f}")
        final_dur = max_seconds
    elif fast_cut_sync:
        final_dur = min(max_seconds, max(1.2, spoken_s + gap_seconds))
    else:
        final_dur = max_seconds

    post_filters.append("apad")
    post_filters.append(f"atrim=0:{final_dur:.3f}")

    proc2 = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(trimmed_wav),
            "-af",
            ",".join(post_filters),
            "-ar",
            "44100",
            "-ac",
            "2",
            str(out_wav),
        ],
        capture_output=True,
        text=True,
        check=False,
        **silent_subprocess_kwargs(),
    )
    trimmed_wav.unlink(missing_ok=True)
    if proc2.returncode != 0:
        raise RuntimeError(f"ffmpeg failed fitting scene audio: {proc2.stderr[-1000:]}")

    return round(final_dur, 3)


def generate_voiceover_and_srt(ep: EpisodeSpec, out_dir: Path) -> tuple[Path, Path]:
    layout = EpisodeLayout.for_episode(out_dir, ep.episode_id)
    layout.ensure_dirs()

    vo_dir = layout.vo_scenes_dir
    mp3_path = layout.audio_dir / "voiceover.mp3"
    srt_path = layout.subtitles_dir / "captions.srt"

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        srt_path.write_text(build_srt(ep), encoding="utf-8")
        full_narration = " ".join(scene.narration_id.strip() for scene in ep.scenes)
        asyncio.run(
            _synthesize_edge_tts(full_narration, ep.tts_voice, ep.tts_rate, ep.tts_pitch, mp3_path)
        )
        return mp3_path, srt_path

    fitted_wavs: list[Path] = []
    scene_durations: list[float] = []

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
        actual_dur = _fit_scene_audio(
            ffmpeg,
            raw_scene_mp3,
            float(scene.duration_seconds),
            fitted_wav,
            pitch_shift=ep.tts_pitch_shift,
            fast_cut_sync=ep.fast_cut_sync,
            gap_seconds=ep.scene_gap_seconds,
        )
        fitted_wavs.append(fitted_wav)
        scene_durations.append(actual_dur)

    # Save exact tight-cut scene timings so assemble_video & SRT stay 100% synced
    (vo_dir / "timings.json").write_text(
        json.dumps({"scene_durations": scene_durations, "fast_cut_sync": ep.fast_cut_sync}, indent=2),
        encoding="utf-8",
    )
    srt_path.write_text(build_srt(ep, scene_durations=scene_durations), encoding="utf-8")

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
        **silent_subprocess_kwargs(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed concatenating voiceover: {proc.stderr[-1000:]}")

    return mp3_path, srt_path


def _escape_ffmpeg_filter_path(path: Path) -> str:
    raw = path.resolve().as_posix()
    return raw.replace(":", r"\:").replace("'", r"\'")


def _load_scene_timings(layout: EpisodeLayout) -> list[float] | None:
    timings_file = layout.vo_scenes_dir / "timings.json"
    if not timings_file.exists():
        return None
    try:
        data = json.loads(timings_file.read_text(encoding="utf-8"))
        durs = data.get("scene_durations")
        if isinstance(durs, list) and durs:
            return [float(x) for x in durs]
    except Exception:
        return None
    return None


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

    resolved_bgm: Path | None = None
    if bgm_path and bgm_path.exists():
        resolved_bgm = bgm_path
    elif ep.bgm_path:
        cand = Path(ep.bgm_path)
        if not cand.is_absolute():
            cand = Path.cwd() / cand
        if cand.exists():
            resolved_bgm = cand

    scene_timings = _load_scene_timings(layout) if ep.fast_cut_sync else None

    norm_dir = layout.clips_norm_dir
    normalized_clips: list[Path] = []
    all_have_audio = True
    total_video_seconds = 0.0

    for idx, clip in enumerate(clips, start=1):
        norm_path = norm_dir / f"norm_{idx:02d}.mp4"
        clip_has_audio = _has_audio_stream(ffmpeg, clip)
        if not clip_has_audio:
            all_have_audio = False

        clip_dur = _probe_duration_seconds(ffmpeg, clip)
        target_trim: float | None = None
        if scene_timings and (idx - 1) < len(scene_timings):
            desired = scene_timings[idx - 1]
            target_trim = min(desired, clip_dur) if clip_dur else desired
            total_video_seconds += target_trim
        else:
            total_video_seconds += clip_dur or float(ep.scenes[min(idx - 1, len(ep.scenes) - 1)].duration_seconds)

        norm_cmd = [ffmpeg, "-y", "-i", str(clip)]
        if not clip_has_audio:
            norm_cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        if target_trim is not None:
            norm_cmd.extend(["-t", f"{target_trim:.3f}"])

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

        proc = subprocess.run(
            norm_cmd,
            capture_output=True,
            text=True,
            check=False,
            **silent_subprocess_kwargs(),
        )
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

    fade_start = max(0.5, total_video_seconds - 1.2)
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
            f"afade=t=in:st=0:d=0.3,"
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

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **silent_subprocess_kwargs(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg assemble failed ({proc.returncode}): {proc.stderr[-1500:]}")
    return output_mp4
