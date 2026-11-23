# Roblox-Meme-Flow

Daily short-form Indonesian meme video pipeline inspired by the **"In This World" ("Di Dunia Ini...")** blocky 3D Roblox-style storytelling format (`9:16` Shorts / Reels / TikTok), powered by **Google Flow** (`gflow-cli`), **`agbelemi/google-flow-scripting-skill`**, **`edge-tts`** (Indonesian voiceover), and **`ffmpeg`**.

---

## Stack & Dual-Model Workflow

- **Gemini 4 Neon (High)** (Antigravity): Pipeline architecture, continuity validation, Google Flow orchestration, final QA.
- **OpenAI GPT-6.2 Sol via Kilo** (`openai/gpt-6.2-sol`): Daily Indonesian comedy ideation (*"Di dunia ini..."*), Gen-Z punchlines, episode YAML drafting, and prompt review.
- **AI Skills:**
  - `.agents/skills/google-flow-scripting/` — Vendored from [`agbelemi/google-flow-scripting-skill`](https://github.com/agbelemi/google-flow-scripting-skill) (MIT) for `@PascalCase` reference handles, storyboard-first workflow, and continuity QA.
  - `.agents/skills/di-dunia-ini-roblox-id/` — Custom Indonesian Roblox-style meme storytelling skill.
- **Google Flow CLI & MCP:** [`ffroliva/gflow-cli`](https://github.com/ffroliva/gflow-cli) driving Veo 3.1 / Omni Flash & Nano Banana over your local signed-in Chrome CDP session with `--no-spend` protection by default.
- **Voiceover & Subtitles:** `edge-tts` (`id-ID-ArdiNeural` / `id-ID-GadisNeural`) + automatic `.srt` meme captions + `ffmpeg` (`imageio-ffmpeg` fallback).

---

## Windows Quick Start

```powershell
cd "C:\Personal Projects\Roblox-Meme-Flow"

# Activate venv & install editable package
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Check local readiness (Python, gflow, ffmpeg, edge-tts, kilo, Chrome CDP)
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli doctor

# Run unit tests
.\.venv\Scripts\python.exe -m pytest -q
```

---

## Daily Episode Workflow

### 1. Validate Episode YAML (Continuity + Safety QA)
```powershell
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli validate episodes\sample_ep01_kursi_kosong.yaml
```

### 2. Export Reference Sheets, Storyboard Prompt, Scene Prompts & SRT
```powershell
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli plan episodes\sample_ep01_kursi_kosong.yaml
```
Outputs go to `outputs/<episode_id>/` (`plan.json`, `storyboard_prompt.txt`, `scene_prompts.md`, `captions.srt`).

### 3. Sign In Once to Google Flow (`gflow auth login`)
First, make sure Playwright's Chromium binary is installed (needed if Google Chrome is not installed on the system):
```powershell
.\.venv\Scripts\playwright.exe install chromium
```
Then authenticate your local Google Flow session once and verify credits:
```powershell
.\.venv\Scripts\gflow.exe auth login
.\.venv\Scripts\gflow.exe auth status
.\.venv\Scripts\gflow.exe credits
```
> **Note:** `gflow-cli` (`v0.105.1`) only supports **Playwright internal Chromium** (`--browser internal`, used automatically when Google Chrome is absent) or **Google Chrome** (`--browser chrome`). Brave/Edge are not natively supported by `gflow auth login`. If Google blocks sign-in in internal Chromium, install Google Chrome and re-run `gflow auth login --browser chrome`.

### 4. Generate Safe Manifest (`--max-credits 0`) or Live Google Flow Run
```powershell
# Safe dry-run manifest (default: --max-credits 0 so 0 video credits are spent)
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli run-flow episodes\sample_ep01_kursi_kosong.yaml

# Execute live generation only after approving storyboard (uses your Flow credits)
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli run-flow episodes\sample_ep01_kursi_kosong.yaml --execute --spend
```

### 5. Synthesize Indonesian Voiceover & Assemble Final 9:16 Video
```powershell
# Generate Indonesian TTS MP3 + timed captions.srt
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli voiceover episodes\sample_ep01_kursi_kosong.yaml

# Stitch Flow clips + VO + burned-in meme captions -> outputs/<episode_id>/final_9x16.mp4
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli assemble episodes\sample_ep01_kursi_kosong.yaml `
  --clips outputs\2026-11-23-ep01-kursi-kosong\clips\scene_01.mp4 `
          outputs\2026-11-23-ep01-kursi-kosong\clips\scene_02.mp4 `
          outputs\2026-11-23-ep01-kursi-kosong\clips\scene_03.mp4 `
          outputs\2026-11-23-ep01-kursi-kosong\clips\scene_04.mp4
```

---

## Safety & Cost Guardrails

- `run-flow` defaults to `--no-spend` so credits are never spent accidentally.
- Never commit `.env`, `chrome-profile/`, `outputs/`, or generated media.
- Auto-uploading to TikTok/Instagram/YouTube is disabled (`ENABLE_AUTO_UPLOAD=false`); review every final MP4 manually before posting.
