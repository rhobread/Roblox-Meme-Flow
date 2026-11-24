from pathlib import Path

from roblox_meme_flow.flow_runner import build_gflow_manifest
from roblox_meme_flow.models import EpisodeSpec, load_episode
from roblox_meme_flow.prompt_builder import (
    build_reference_prompts,
    build_scene_video_prompts,
    build_srt,
    build_storyboard_prompt,
    export_plan,
)
from roblox_meme_flow.validator import has_errors, validate_episode

EPISODES_DIR = Path(__file__).resolve().parent.parent / "episodes"
SAMPLE_EPISODE = EPISODES_DIR / "sample_ep01_kursi_kosong.yaml"


def test_all_episodes_pass_validation() -> None:
    episode_files = sorted(EPISODES_DIR.glob("*.yaml"))
    assert len(episode_files) >= 5
    for path in episode_files:
        ep = load_episode(path)
        issues = validate_episode(ep)
        assert not issues, f"Unexpected issues in {path.name}: {issues}"
        assert ep.total_duration_seconds == 24


def test_storyboard_prompt_starts_with_hard_rule() -> None:
    ep = load_episode(SAMPLE_EPISODE)
    prompt = build_storyboard_prompt(ep)
    assert prompt.startswith("GENERATE THE STORYBOARD IMAGE NOW.")
    assert "2x2" in prompt
    assert "@Raka" in prompt
    assert "@WarkopMalam" in prompt


def test_validator_catches_em_dash_and_missing_handle() -> None:
    ep = load_episode(SAMPLE_EPISODE)
    bad = ep.model_copy(deep=True)
    bad.scenes[0].narration_id = "Di dunia ini — ada em dash."
    bad.scenes[0].visual_prompt = "Inside @KamarKosRaka, a character lies on bed without handle."
    issues = validate_episode(bad)
    codes = {i.code for i in issues}
    assert "NO_EM_DASH" in codes
    assert "MISSING_HANDLE_IN_PROMPT" in codes
    assert has_errors(issues)


def test_validator_warns_on_raw_trademark_in_visual() -> None:
    ep = load_episode(SAMPLE_EPISODE)
    bad = ep.model_copy(deep=True)
    bad.scenes[0].visual_prompt = (
        "Inside @KamarKosRaka, Roblox avatar @Raka lies on the bed tapping a phone."
    )
    issues = validate_episode(bad)
    assert any(i.code == "TRADEMARK_IN_VISUAL" and i.severity == "warning" for i in issues)


def test_gflow_manifest_defaults_to_zero_max_credits_and_strips_at(tmp_path: Path) -> None:
    ep = load_episode(SAMPLE_EPISODE)
    manifest = build_gflow_manifest(ep, tmp_path / ep.episode_id, spend=False)
    assert manifest["spend_enabled"] is False
    image_cmds = [c for c in manifest["commands"] if c["stage"] == "reference_image"]  # type: ignore[index]
    assert image_cmds[0]["args"][1:3] == ["image", "t2i"]
    assert "@" not in str(image_cmds[0]["prompt"])
    storyboard_cmd = [c for c in manifest["commands"] if c["stage"] == "storyboard"][0]  # type: ignore[index]
    assert storyboard_cmd["args"][1:3] == ["image", "gen"]
    assert "--ref" in storyboard_cmd["args"]
    assert "@" not in str(storyboard_cmd["prompt"])
    video_cmds = [c for c in manifest["commands"] if c["stage"] == "video_scene"]  # type: ignore[index]
    assert len(video_cmds) == 4
    for cmd in video_cmds:
        args = cmd["args"]
        assert args[1:3] == ["video", "gen"]
        assert "--max-credits" in args
        idx = args.index("--max-credits")
        assert args[idx + 1] == "0"
        assert "--ref" in args
        assert "@" not in str(cmd["prompt"])


def test_export_plan_and_srt_generation(tmp_path: Path) -> None:
    ep = load_episode(SAMPLE_EPISODE)
    ep_dir = export_plan(ep, tmp_path, source_yaml=SAMPLE_EPISODE)
    assert (ep_dir / "01_final").is_dir()
    assert (ep_dir / "02_clips").is_dir()
    assert (ep_dir / "03_images" / "refs").is_dir()
    assert (ep_dir / "04_audio").is_dir()
    assert (ep_dir / "05_subtitles" / "captions.srt").exists()
    assert (ep_dir / "06_scripts" / "plan.json").exists()
    assert (ep_dir / "06_scripts" / "storyboard_prompt.txt").exists()
    assert (ep_dir / "06_scripts" / "scene_prompts.md").exists()
    assert (ep_dir / "06_scripts" / SAMPLE_EPISODE.name).exists()
    assert (ep_dir / "99_logs").is_dir()

    refs = build_reference_prompts(ep)
    assert "@Raka" in refs and "@WarkopMalam" in refs

    scenes = build_scene_video_prompts(ep)
    assert len(scenes) == 4

    srt = build_srt(ep)
    assert "00:00:00,000 -->" in srt
    assert "DI DUNIA INI" in srt
