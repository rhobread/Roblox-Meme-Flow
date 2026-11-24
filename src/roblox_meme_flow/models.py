from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

DEFAULT_STYLE_BIBLE = (
    "Stylized 3D blocky plastic game-avatar animation, smooth glossy toy-like R6/R15 "
    "cubic characters with simple expressive printed faces, bright clean indie-game lighting, "
    "crisp shadows, zero on-screen text or watermarks, vertical 9:16 framing."
)


class CharacterAsset(BaseModel):
    handle: str = Field(..., description="Canonical @PascalCase handle, e.g. @Budi")
    role: str
    visual_description: str
    wardrobe: str
    expression_default: str = "deadpan wide-eyed plastic stare"


class LocationAsset(BaseModel):
    handle: str = Field(..., description="Canonical @PascalCase handle, e.g. @WarkopMalam")
    visual_description: str
    lighting: str
    key_props: list[str] = Field(default_factory=list)


class SceneSpec(BaseModel):
    scene_number: int = Field(..., ge=1)
    beat: Literal["hook", "escalation", "twist", "outro"]
    duration_seconds: Literal[4, 6, 8, 10] = 6
    characters: list[str] = Field(default_factory=list)
    location: str
    narration_id: str = Field(..., min_length=5)
    subtitle_override: Optional[str] = None
    visual_prompt: str = Field(..., min_length=15)
    camera: str = "medium vertical shot, subtle handheld comedic zoom"
    audio_sfx: str = "subtle ambient game sound effects, comedic pop"


class EpisodeSpec(BaseModel):
    episode_id: str = Field(..., min_length=3)
    title_id: str
    world_rule_id: str
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    image_model: str = "nano-2.1"
    video_model: str = "omni-1.2-flash"
    tts_voice: str = "id-ID-ArdiNeural"
    tts_rate: str = "+16%"
    tts_pitch: str = "+28Hz"
    tts_pitch_shift: float = Field(
        default=1.18,
        ge=0.75,
        le=1.5,
        description="FFmpeg pitch shift multiplier (1.0=normal, 1.12-1.25=comedic Roblox meme pitch).",
    )
    style_bible: str = DEFAULT_STYLE_BIBLE
    characters: list[CharacterAsset] = Field(..., min_length=1)
    locations: list[LocationAsset] = Field(..., min_length=1)
    scenes: list[SceneSpec] = Field(..., min_length=2, max_length=9)

    @property
    def total_duration_seconds(self) -> int:
        return sum(scene.duration_seconds for scene in self.scenes)


def load_episode(path: Path) -> EpisodeSpec:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return EpisodeSpec.model_validate(raw)
