from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EpisodeLayout:
    """Standard per-episode folder layout separating every video element."""

    root: Path
    final_dir: Path
    clips_dir: Path
    images_dir: Path
    refs_dir: Path
    audio_dir: Path
    vo_scenes_dir: Path
    subtitles_dir: Path
    scripts_dir: Path
    logs_dir: Path
    clips_norm_dir: Path

    @classmethod
    def for_episode(cls, out_dir: Path, episode_id: str) -> EpisodeLayout:
        root = out_dir / episode_id
        images_dir = root / "03_images"
        audio_dir = root / "04_audio"
        logs_dir = root / "99_logs"
        return cls(
            root=root,
            final_dir=root / "01_final",
            clips_dir=root / "02_clips",
            images_dir=images_dir,
            refs_dir=images_dir / "refs",
            audio_dir=audio_dir,
            vo_scenes_dir=audio_dir / "scenes",
            subtitles_dir=root / "05_subtitles",
            scripts_dir=root / "06_scripts",
            logs_dir=logs_dir,
            clips_norm_dir=logs_dir / "clips_norm",
        )

    def ensure_dirs(self) -> None:
        for d in (
            self.root,
            self.final_dir,
            self.clips_dir,
            self.images_dir,
            self.refs_dir,
            self.audio_dir,
            self.vo_scenes_dir,
            self.subtitles_dir,
            self.scripts_dir,
            self.logs_dir,
            self.clips_norm_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
