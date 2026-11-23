# Project Context — Roblox-Meme-Flow

## 1. Goal

Build a reliable, semi-automated **daily Indonesian meme video studio** producing 15–30 second vertical (`9:16`) narrative comedy videos in the viral **"In This World" / "Di Dunia Ini..."** blocky 3D Roblox-avatar storytelling format.

## 2. Format Anatomy ("Di Dunia Ini..." Indonesia)

1. **Hook (0–4s):** Immediately states one absurd, hyper-specific rule of the world in punchy Indonesian (*"Di dunia ini, siapa pun yang bilang 'otw' padahal masih tiduran langsung melayang ke langit..."*).
2. **Escalation (4–12s):** A blocky 3D avatar tries to live normally or cheat the rule in an everyday Indonesian setting (warkop, kosan, kelas, jalanan macet).
3. **Climax & Plot Twist (12–22s):** The rule backfires in an exaggerated, meme-worthy physical gag with deadpan Roblox-style facial expressions.
4. **Loop / Punchline Outro (22–26s):** Fast comedic payoff that encourages replays and comments.

## 3. Recommended Tech Stack

| Layer | Tool / Package | Why |
| :--- | :--- | :--- |
| **Episode Spec & Validation** | Python 3.13 + Pydantic + PyYAML | Strictly validates `@PascalCase` continuity handles, duration budgets, safety rules, and Indonesian narration before spending any Flow credits. |
| **Scripting & Continuity Skill** | `agbelemi/google-flow-scripting-skill` (vendored in `.agents/skills/google-flow-scripting/`) | Enforces canonical `@ReferenceHandles`, storyboard-first approval (`GENERATE THE STORYBOARD IMAGE NOW.`), and zero continuity drift across scenes. |
| **Comedy & Prompt Skill** | Custom `.agents/skills/di-dunia-ini-roblox-id/SKILL.md` | Encodes Indonesian meme rhythm, blocky-plastic avatar art direction (trademark-safe visual wording), and short-form pacing. |
| **Google Flow Execution** | `ffroliva/gflow-cli` (`gflow` CLI + MCP server) | Mature Windows-compatible CLI & MCP server for Veo 3.1, Omni Flash, and Nano Banana over real Chrome CDP with built-in `--no-spend` protection. |
| **Indonesian Voiceover** | `edge-tts` (`id-ID-ArdiNeural` / `id-ID-GadisNeural`) | Free, natural Indonesian neural TTS with fast comedic pacing control (`rate`, `pitch`). |
| **Video Stitching & Subtitles** | `ffmpeg` (`imageio-ffmpeg` fallback) | Concatenates Flow clips, mixes VO audio, burns bold centered meme subtitles, and exports `1080x1920` H.264 MP4. |
| **Dual-Model AI Workflow** | **Gemini 4 Neon (High)** + **OpenAI GPT-6.2 Sol (via Kilo)** | Orchestrated in T3 Code; Neon High leads pipeline/continuity QA while GPT-6.2 Sol drafts/sharpens Indonesian comedy specs and reviews prompts. |
| **Daily Scheduling** | T3 Code Scheduled Tasks (`/schedule`) or Windows Task Scheduler | Generates daily episode YAML, runs validation & optional storyboard/video prep at a fixed WIB time. |

## 4. Pipeline Flow

```text
Daily Idea & Episode YAML (Neon High + GPT-6.2 Sol via Kilo)
        │
        ▼
Pre-Generation QA (`rmf validate`) ──► Blocks drift / em dashes / raw trademark terms
        │
        ▼
Prompt & Manifest Export (`rmf plan`) ──► Reference sheets + Storyboard + Scene prompts
        │
        ▼
Google Flow Generation (`rmf run-flow`) ──► Defaults to `--no-spend`; `--spend` generates via Chrome CDP
        │
        ▼
Indonesian VO + Subtitles (`rmf voiceover`) ──► `edge-tts` MP3 + timed `.srt`
        │
        ▼
Final Render (`rmf assemble`) ──► `outputs/<episode_id>/final_9x16.mp4` (Ready for manual review & upload)
```
