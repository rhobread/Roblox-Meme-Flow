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

## Cara Paling Mudah (Web UI Studio & `run.ps1`)

Buka PowerShell di `C:\Personal Projects\Roblox-Meme-Flow` (atau klik tombol **Studio Web UI** di toolbar T3 Code):

```powershell
# Buka Studio Web UI di browser (http://127.0.0.1:8787)
.\run.ps1 ui

# Atau langsung dari terminal:
.\run.ps1 list                                          # Lihat semua script episode
.\run.ps1 credits                                       # Cek saldo kredit Google Flow (0 kredit)
.\run.ps1 research                                      # Riset tren viral Indonesia + prompt T3
.\run.ps1 preview episodes\viral_ep01_utang_strobo.yaml # STEP 1 (0 kredit): Gambar + Storyboard + VO
.\run.ps1 render  episodes\viral_ep01_utang_strobo.yaml # STEP 2 (limit 50 cr/hari): Video + BGM + Subtitle
.\run.ps1 revoice episodes\viral_ep01_utang_strobo.yaml # Ganti suara/BGM saja (0 kredit)
.\run.ps1 open    episodes\viral_ep01_utang_strobo.yaml # Buka folder episode di File Explorer
```

### Limitasi Kredit Harian (1 Video/Hari Selamanya)
Google Flow menambah **+50 kredit/hari**. Dengan `omni-1.2-flash` (`3 kredit/detik`):
- **Preset Hemat `hemat_50` (Rekomendasi):** **4 scene x 4 detik = 16 detik = 48 kredit** (<= 50/hari, net +2 kredit/hari — **1 video setiap hari selamanya** tanpa menguras saldo utama!).
- **Preset 3 Scene `hemat_3scene`:** **3 scene x 5 detik = 15 detik = 45 kredit** (<= 50/hari).
- **Preset Seimbang `seimbang_60`:** **4 scene x 5 detik = 20 detik = 60 kredit** (net -10/hari dari saldo).
- **Preset Full `full_72`:** **4 scene x 6 detik = 24 detik = 72 kredit** (net -22/hari dari saldo).

---

## Windows Quick Start (Manual CLI)

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
.\.venv\Scripts\gflow.exe credits user
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
