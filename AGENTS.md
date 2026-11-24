# Project Instructions — Roblox-Meme-Flow

## Shared Instructions

Read `../AGENTS.md` at the `C:\Personal Projects` workspace root first. It contains standing read access, key/credential privacy, Git publishing defaults, and server/deployment boundaries. Follow those shared rules alongside all project-specific rules below.

## Project Purpose

Daily short-form Indonesian meme video pipeline inspired by the **"In This World" ("Di Dunia Ini...")** blocky 3D Roblox-style storytelling format (`9:16` vertical Shorts/Reels/TikTok), powered by **Google Flow** (Nano Banana / Imagen + Veo 3.1 / Omni Flash), local Indonesian TTS (`edge-tts`), and `ffmpeg` assembly.

Read `PROJECT_CONTEXT.md` before modifying architecture, schemas, or automation workflows.

## Dual-Model Collaboration

This project is designed to leverage two AI models together via T3 Code / Kilo Code:

1. **Gemini 4 Neon (High)** (Antigravity):
   - Primary orchestrator, architecture/pipeline engineer, Google Flow continuity auditor, and final QA reviewer.
2. **OpenAI GPT-6.2 Sol via Kilo** (`providerInstanceId: acpRegistry_kilo`, `model: openai/gpt-6.2-sol`):
   - Creative Indonesian comedy writer (absurd "Di dunia ini..." premises, Gen-Z Indonesian phrasing, punchy plot twists), secondary code/prompt reviewer, and episode spec generator.

## Installed AI Skills

Always read and apply the relevant project skills before writing episode scripts or Google Flow prompts:

- `.agents/skills/google-flow-scripting/SKILL.md` — Continuity rules (`@PascalCase` handles, no em dashes, storyboard-first workflow, `GENERATE THE STORYBOARD IMAGE NOW.`, pre-generation validation).
- `.agents/skills/di-dunia-ini-roblox-id/SKILL.md` — Indonesian "Di Dunia Ini..." blocky-avatar comedy structure, visual style guardrails (avoid raw trademark terms in visual prompts), hook/twist pacing, and TTS/subtitle conventions.
- `.agents/skills/kids-animation-id/SKILL.md` & `.agents/skills/ai-kids-cartoon-videos/SKILL.md` — Family-friendly Indonesian 3D kids animation rules (YouTube Kids/Shorts/Reels safe, bright pastel toy/cartoon aesthetics, <= 50 daily credits budget).

## Safety, Cost, And Credit Boundaries

- **Google Flow Credit Protection & Daily Budget (<= 50 Credits/Day):** `flow_runner` MUST default to manifest-only dry-run with `--max-credits 0` (`FLOW_DRY_RUN=true`). Live renders enforce `credit_guard.py` (`DAILY_CREDIT_LIMIT=50`, `MAX_VIDEOS_PER_DAY=1`) matching Google Flow's +50 daily refill (default sustainable budget: **4 scenes x 4s = 48 credits** on `omni-1.2-flash`). Never override limits or spend credits without explicit user approval.
- **Google Account Safety:** Use `gflow-cli` attached to the operator's own signed-in Chrome CDP session. Never ask for, log, print, or store Google passwords, cookies, or session tokens in repo files.
- **No Unapproved Auto-Publishing:** Generating videos locally is NOT authorization to auto-upload to TikTok, Instagram, or YouTube. Keep `ENABLE_AUTO_UPLOAD=false`; always output finished videos to `outputs/<episode_id>/` for human review first.
- **No Unapproved Paid APIs:** Default TTS (`edge-tts`) and assembly (`imageio-ffmpeg` / `ffmpeg`) are zero-cost local tools. Do not introduce paid third-party APIs without explicit owner approval.
- **Timezone:** Use `Asia/Jakarta` (WIB) for daily schedules and episode date IDs.

## Working & Validation Rules

- Keep all operational logic in typed Python under `src/roblox_meme_flow/`.
- Never claim a live Google Flow render succeeded unless it was actually executed against a logged-in Chrome CDP session.
- Validate changes before committing:
  - `.\.venv\Scripts\python.exe -m pytest -q`
  - `.\.venv\Scripts\python.exe -m roblox_meme_flow.cli validate episodes\sample_ep01_kursi_kosong.yaml`
- Never commit `.env`, `.venv/`, `outputs/`, generated media (`*.mp4`, `*.mp3`, `*.png`), or Chrome profile data.

## Publishing And Deployment

- Target GitHub repository: `https://github.com/rhobread/Roblox-Meme-Flow` (once created on GitHub).
- Follow `../AGENTS.md` publishing rules: commit only clean, public-safe source/docs/tests and push normally when the remote exists.
- No VPS/server deployment target is configured; this pipeline runs locally on Windows alongside the user's Chrome CDP session.
