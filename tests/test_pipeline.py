from pathlib import Path

from fastapi.testclient import TestClient

from roblox_meme_flow.credit_guard import (
    DailyBudgetPolicy,
    check_render_budget,
    estimate_episode_credits,
    record_render_spend,
)
from roblox_meme_flow.desktop_launcher import should_auto_shutdown
from roblox_meme_flow.flow_runner import build_gflow_manifest
from roblox_meme_flow.models import EpisodeSpec, load_episode
from roblox_meme_flow.prompt_builder import (
    build_reference_prompts,
    build_scene_video_prompts,
    build_srt,
    build_storyboard_prompt,
    export_plan,
)
from roblox_meme_flow.researcher import build_viral_research_brief
from roblox_meme_flow.script_gen import (
    build_antigravity_cmd,
    build_t3_generation_prompt,
    extract_oauth_code,
    sanitize_episode_dict,
    validate_and_save_yaml,
)
from roblox_meme_flow.validator import has_errors, validate_episode
from roblox_meme_flow.web_ui import create_app
from roblox_meme_flow.win_silent import is_gflow_playwright_executable, should_hide_gflow_window

EPISODES_DIR = Path(__file__).resolve().parent.parent / "episodes"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_EPISODE = FIXTURES_DIR / "sample_ep01_kursi_kosong.yaml"
KIDS_EPISODE = FIXTURES_DIR / "kids_ep01_awan_pelangi.yaml"


def test_all_episodes_pass_validation() -> None:
    episode_files = sorted(EPISODES_DIR.glob("*.yaml"))
    assert len(episode_files) >= 1
    for path in episode_files:
        ep = load_episode(path)
        issues = validate_episode(ep)
        assert not issues, f"Unexpected issues in {path.name}: {issues}"
        assert 12 <= ep.total_duration_seconds <= 52


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


def test_credit_guard_enforces_daily_50_credit_and_1_video_limit(tmp_path: Path) -> None:
    ledger = tmp_path / "credit_ledger.json"
    policy = DailyBudgetPolicy(daily_credit_limit=50, max_videos_per_day=1, daily_refill_credits=50)

    kids_ep = load_episode(KIDS_EPISODE)  # 4x4s = 48 credits
    assert estimate_episode_credits(kids_ep) == 48
    ok = check_render_budget(kids_ep, ledger, live_balance=978, policy=policy)
    assert ok.allowed is True
    assert ok.net_daily_delta == 2
    assert ok.estimated_runway_days == 9999

    long_ep = load_episode(SAMPLE_EPISODE)  # 4x6s = 72 credits
    assert estimate_episode_credits(long_ep) == 72
    blocked = check_render_budget(long_ep, ledger, live_balance=978, policy=policy)
    assert blocked.allowed is False

    overridden = check_render_budget(long_ep, ledger, live_balance=978, policy=policy, override_limit=True)
    assert overridden.allowed is True

    record_render_spend(ledger, kids_ep.episode_id, 48)
    second_same_day = check_render_budget(kids_ep, ledger, live_balance=930, policy=policy)
    assert second_same_day.allowed is False
    assert second_same_day.videos_rendered_today == 1


def test_viral_research_and_t3_prompt_generation() -> None:
    brief = build_viral_research_brief(content_mode="kids_animation_id", topic_hint="pelangi", fetch_live=False)
    assert "youtube_shorts" in brief.algorithm_rules
    assert "tiktok_fyp" in brief.algorithm_rules
    assert "instagram_reels" in brief.algorithm_rules

    prompt, _ = build_t3_generation_prompt(
        project_root=EPISODES_DIR.parent,
        content_mode="kids_animation_id",
        budget_preset="hemat_50",
        voice_preset="preset_d",
        topic_hint="pelangi",
        research_brief=brief,
    )
    assert "kids-animation-id" in prompt
    assert "48 kredit" in prompt
    assert "in_this_town_bgm.mp3" in prompt


def test_web_ui_endpoints(tmp_path: Path) -> None:
    app = create_app(EPISODES_DIR.parent)
    client = TestClient(app)

    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "Roblox-Meme-Flow Studio" in r_home.text
    assert 'id="epSort"' in r_home.text

    r_status = client.get("/api/status?refresh_credits=false")
    assert r_status.status_code == 200
    status_data = r_status.json()
    assert "long_veo_80" in status_data["budget_presets"]
    assert "antigravity" in status_data["ai_engines"]
    assert "kids-animation-id" in status_data["skills"]

    r_eps = client.get("/api/episodes")
    assert r_eps.status_code == 200
    eps = r_eps.json()["episodes"]
    assert len(eps) >= 1

    first_filename = eps[0]["filename"]
    r_ep = client.get(f"/api/episodes/{first_filename}")
    assert r_ep.status_code == 200
    assert r_ep.json()["estimated_credits"] > 0


def test_web_ui_delete_episode_removes_yaml_and_all_outputs(tmp_path: Path) -> None:
    ep_dir = tmp_path / "episodes"
    out_dir = tmp_path / "outputs" / "2026-11-24-temp-del" / "01_final"
    ep_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    sample_yaml = KIDS_EPISODE.read_text(encoding="utf-8").replace(
        "2026-11-24-kids01-awan-pelangi", "2026-11-24-temp-del"
    )
    yaml_file = ep_dir / "temp_del.yaml"
    yaml_file.write_text(sample_yaml, encoding="utf-8")
    dummy_mp4 = out_dir / "final_9x16.mp4"
    dummy_mp4.write_bytes(b"0" * 1024 * 512)  # 0.5 MB

    app = create_app(tmp_path)
    client = TestClient(app)
    res = client.delete("/api/episodes/temp_del.yaml")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["freed_mb"] >= 0.5
    assert not yaml_file.exists()
    assert not (tmp_path / "outputs" / "2026-11-24-temp-del").exists()


def test_win_silent_never_hides_minimized_user_apps_only_gflow_playwright() -> None:
    pw_chrome = r"C:\Users\rober\AppData\Local\ms-playwright\chromium-1228\chrome-win64\chrome.exe"
    assert is_gflow_playwright_executable(pw_chrome) is True
    assert is_gflow_playwright_executable(r"C:\Program Files\Microsoft VS Code\Code.exe") is False
    assert is_gflow_playwright_executable(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") is False
    assert is_gflow_playwright_executable(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe") is False
    assert is_gflow_playwright_executable(r"C:\Program Files\Google\Chrome\Application\chrome.exe") is False

    # Minimized user apps sit at (-32000, -32000) on Windows — must NEVER be hidden!
    for user_exe in (
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ):
        assert (
            should_hide_gflow_window(
                class_name="Chrome_WidgetWin_1",
                is_visible=True,
                is_iconic=True,
                rect_left=-32000,
                rect_top=-32000,
                exe_path=user_exe,
                pid=1234,
                allowed_pids={1234},
            )
            is False
        )
        # Even if not iconic and somehow off-screen, user apps must NEVER be hidden.
        assert (
            should_hide_gflow_window(
                class_name="Chrome_WidgetWin_1",
                is_visible=True,
                is_iconic=False,
                rect_left=-30000,
                rect_top=-30000,
                exe_path=user_exe,
                pid=1234,
                allowed_pids={1234},
            )
            is False
        )

    # Playwright Chromium outside gflow's PID tree must NOT be hidden.
    assert (
        should_hide_gflow_window(
            class_name="Chrome_WidgetWin_1",
            is_visible=True,
            is_iconic=False,
            rect_left=-30000,
            rect_top=-30000,
            exe_path=pw_chrome,
            pid=9999,
            allowed_pids={1000, 1001},
        )
        is False
    )

    # Playwright Chromium inside gflow's PID tree, not minimized, off-screen (-30000, -30000) -> hide.
    assert (
        should_hide_gflow_window(
            class_name="Chrome_WidgetWin_1",
            is_visible=True,
            is_iconic=False,
            rect_left=-30000,
            rect_top=-30000,
            exe_path=pw_chrome,
            pid=1001,
            allowed_pids={1000, 1001},
        )
        is True
    )

    # Playwright Chromium that is on-screen or iconic -> do NOT hide.
    assert (
        should_hide_gflow_window(
            class_name="Chrome_WidgetWin_1",
            is_visible=True,
            is_iconic=False,
            rect_left=100,
            rect_top=100,
            exe_path=pw_chrome,
            pid=1001,
            allowed_pids={1000, 1001},
        )
        is False
    )
    assert (
        should_hide_gflow_window(
            class_name="Chrome_WidgetWin_1",
            is_visible=True,
            is_iconic=True,
            rect_left=-32000,
            rect_top=-32000,
            exe_path=pw_chrome,
            pid=1001,
            allowed_pids={1000, 1001},
        )
        is False
    )


def test_desktop_launcher_auto_shutdown_and_heartbeat_endpoints() -> None:
    # Active browser window open -> never auto-shutdown
    assert (
        should_auto_shutdown(
            now=100.0,
            started_at=0.0,
            last_heartbeat=95.0,
            ui_closed_at=None,
            browser_exited=False,
            has_running_jobs=False,
        )
        is False
    )
    # UI closed within F5 reload grace (<4s) -> wait
    assert (
        should_auto_shutdown(
            now=102.0,
            started_at=0.0,
            last_heartbeat=99.0,
            ui_closed_at=100.0,
            browser_exited=False,
            has_running_jobs=False,
        )
        is False
    )
    # UI closed past grace (>=4s) and idle -> auto-shutdown
    assert (
        should_auto_shutdown(
            now=105.0,
            started_at=0.0,
            last_heartbeat=99.0,
            ui_closed_at=100.0,
            browser_exited=False,
            has_running_jobs=False,
        )
        is True
    )
    # Active render job running -> never kill mid-render even if window closed
    assert (
        should_auto_shutdown(
            now=200.0,
            started_at=0.0,
            last_heartbeat=99.0,
            ui_closed_at=100.0,
            browser_exited=True,
            has_running_jobs=True,
        )
        is False
    )
    # Browser exited and heartbeat timed out (>=20s) -> auto-shutdown
    assert (
        should_auto_shutdown(
            now=130.0,
            started_at=0.0,
            last_heartbeat=100.0,
            ui_closed_at=None,
            browser_exited=True,
            has_running_jobs=False,
        )
        is True
    )

    app = create_app(EPISODES_DIR.parent)
    client = TestClient(app)
    r_hb = client.post("/api/heartbeat")
    assert r_hb.status_code == 200
    assert r_hb.json()["ok"] is True
    assert app.state.lifecycle_snapshot()["ui_closed_at"] is None

    r_close = client.post("/api/ui-closing")
    assert r_close.status_code == 200
    assert app.state.lifecycle_snapshot()["ui_closed_at"] is not None

    # Subsequent heartbeat (e.g. after F5 refresh) clears ui_closed_at
    r_hb2 = client.post("/api/heartbeat")
    assert r_hb2.status_code == 200
    assert app.state.lifecycle_snapshot()["ui_closed_at"] is None


def test_script_gen_antigravity_cmd_and_auto_sanitizer(tmp_path: Path) -> None:
    # --print MUST receive the prompt directly, never --model
    cmd = build_antigravity_cmd("agy.exe", "Buat script", model="gemini-4-neon", effort="high")
    print_idx = cmd.index("--print")
    assert cmd[print_idx + 1] == "Buat script"
    assert cmd[cmd.index("--model") + 1] == "gemini-4-neon"

    # Auto-sanitizer repairs em dashes, raw trademark words, beat aliases, and missing handles
    messy_yaml = """```yaml
episode_id: "2026-11-24-test-auto-fix"
title_id: "Di Dunia Ini — Utang Bikin Melayang"
world_rule_id: "Di dunia ini — siapa yang lupa bayar utang langsung melayang."
content_mode: "meme_roblox_id"
video_model: "veo-lite"
characters:
  - handle: "budi_kos"
    role: "Anak kos"
    visual_description: "Roblox blocky character in yellow"
    wardrobe: "blue shirt"
locations:
  - handle: "@warkop_malam"
    visual_description: "Indonesian warkop Roblox map"
    lighting: "warm lamp"
scenes:
  - scene_number: 1
    beat: "opening"
    duration_seconds: 6
    characters: ["budi_kos"]
    location: "@warkop_malam"
    narration_id: "Di dunia ini — lupa bayar utang langsung melayang tinggi!"
    visual_prompt: "A blocky Roblox character floats upward holding instant noodles."
  - scene_number: 2
    beat: "punchline"
    duration_seconds: 6
    characters: ["budi_kos"]
    location: "@warkop_malam"
    narration_id: "Akhirnya Budi nyangkut di plafon warkop sambil dadah-dadah!"
    visual_prompt: "Smiling wildly near ceiling with @GhostTypo watching."
```"""
    saved = validate_and_save_yaml(messy_yaml, tmp_path / "episodes", auto_sanitize=True)
    assert saved["filename"] == "2026-11-24-test-auto-fix.yaml"
    loaded = load_episode(Path(str(saved["path"])))
    issues = validate_episode(loaded)
    assert not issues, f"Expected zero issues after auto_sanitize, got: {issues}"
    assert loaded.characters[0].handle == "@BudiKos"
    assert loaded.locations[0].handle == "@WarkopMalam"
    assert loaded.scenes[0].beat == "hook"
    assert loaded.scenes[1].beat == "outro"
    assert "@BudiKos" in loaded.scenes[0].visual_prompt
    assert "@WarkopMalam" in loaded.scenes[0].visual_prompt
    assert "@GhostTypo" not in loaded.scenes[1].visual_prompt

    # OAuth code extraction accepts both raw code and full Google redirect URL
    assert extract_oauth_code("4/0AeanS0_abc123") == "4/0AeanS0_abc123"
    assert (
        extract_oauth_code("https://antigravity.google/oauth-callback?state=xyz&code=4%2F0AeanS0_abc123&scope=email")
        == "4/0AeanS0_abc123"
    )


def test_edge_tts_retry_recovers_from_transient_zero_byte_failure(monkeypatch, tmp_path: Path) -> None:
    from roblox_meme_flow import audio_video

    attempts = {"n": 0}

    async def fake_synth(text: str, voice: str, rate: str, pitch: str, out_mp3: Path) -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            out_mp3.write_bytes(b"")  # simulate 0-byte drop
            return
        if attempts["n"] == 2:
            raise RuntimeError("transient websocket disconnect")
        out_mp3.write_bytes(b"ID3" + b"\x00" * 512)

    monkeypatch.setattr(audio_video, "_synthesize_edge_tts", fake_synth)
    monkeypatch.setattr(audio_video.time, "sleep", lambda _s: None)

    out = tmp_path / "scene_03_raw.mp3"
    audio_video._synthesize_edge_tts_with_retry("halo", "id-ID-ArdiNeural", "+18%", "+28Hz", out)
    assert attempts["n"] == 3
    assert out.exists() and out.stat().st_size > 128


def test_veo_lite_r2v_omits_duration_and_caps_storyboard_refs(tmp_path: Path) -> None:
    ep = load_episode(EPISODES_DIR / "viral_ep04_wifi_tetangga_fast.yaml")
    assert ep.video_model == "veo-lite"
    manifest = build_gflow_manifest(ep, tmp_path / ep.episode_id, spend=True, max_credits_per_clip=10)
    video_cmds = [c for c in manifest["commands"] if c["stage"] == "video_scene"]  # type: ignore[index]
    assert len(video_cmds) == 8
    for cmd in video_cmds:
        args = cmd["args"]
        assert "--ref" in args
        # Veo R2V MUST omit --duration so Google Flow pins 8s cleanly without exit 11
        assert "--duration" not in args
        assert "--max-credits" in args and args[args.index("--max-credits") + 1] == "10"

    # Omni model with --ref keeps --duration
    omni_ep = load_episode(KIDS_EPISODE)
    omni_manifest = build_gflow_manifest(omni_ep, tmp_path / omni_ep.episode_id, spend=False)
    omni_videos = [c for c in omni_manifest["commands"] if c["stage"] == "video_scene"]  # type: ignore[index]
    assert "--duration" in omni_videos[0]["args"]

    # Storyboard caps --ref uploads to at most 4 even when episode has >4 total refs
    big_ep = ep.model_copy(deep=True)
    big_ep.characters.append(
        ep.characters[0].model_copy(update={"handle": "@IbuKos"})
    )
    big_ep.locations.append(
        ep.locations[0].model_copy(update={"handle": "@WarungPojok"})
    )
    big_ep.locations.append(
        ep.locations[0].model_copy(update={"handle": "@PosRonda"})
    )
    big_manifest = build_gflow_manifest(big_ep, tmp_path / big_ep.episode_id, spend=False)
    sb = [c for c in big_manifest["commands"] if c["stage"] == "storyboard"][0]  # type: ignore[index]
    assert sb["args"].count("--ref") <= 4





