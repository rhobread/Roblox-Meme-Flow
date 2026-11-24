---
name: di-dunia-ini-roblox-id
description: Writes daily Indonesian "Di Dunia Ini..." (In This World) blocky 3D plastic game-avatar meme episodes, formatted as validated YAML for Google Flow (Nano Banana + Omni 1.2 Flash / Veo 3.1), edge-tts Indonesian voiceover, and ffmpeg 9:16 vertical Shorts/Reels/TikTok.
---

# Di Dunia Ini — Indonesian Blocky Avatar Meme Skill

Use this Skill together with `.agents/skills/google-flow-scripting/SKILL.md` to create **fast-paced 30-45 second** daily Indonesian meme storytelling episodes (`9:16` vertical) within the **80-85 daily Flow credit budget**.

## 1. Core Formula ("In This World" Indonesia — Fast-Paced 7-9 Scenes)

Every default episode uses **8 scenes x 6s (`veo-lite`, ~80 credits, ~35-45s after fast-cut)** or **7-9 rapid scenes (`omni-1.2-flash`, 81-84 credits)** with continuous, energetic Indonesian narration and **zero dead pauses** (`fast_cut_sync: true`, `scene_gap_seconds: 0.10`):

1. **`hook` (Scene 1):**
   - Narration MUST open with `"Di dunia ini, ..."` or `"Di kota ini, ..."` followed by ONE absurd, hyper-specific rule rooted in Indonesian everyday life (kosan, warkop, ojol, macet, gajian, hutang, WiFi tetangga, nongkrong, sekolah/kuliah, kantor, grup WA).
   - Visual immediately shows the rule activating on a deadpan blocky avatar at frame 1.
2. **`setup` (Scene 2):**
   - Introduce the relatable Indonesian character situation and why they try to challenge or ignore the rule.
3. **`escalation` (Scene 3):**
   - The rule triggers visually in an exaggerated, funny way.
4. **`complication` (Scene 4):**
   - Someone else (Pak RT, Bu Warung, teman tongkrongan, bos) notices and raises the stakes immediately.
5. **`climax` (Scene 5):**
   - Protagonist attempts a hilarious desperate cover-up that fails spectacularly.
6. **`twist` (Scene 6):**
   - Unexpected Indonesian karma or absurd plot twist flipping the whole situation upside down!
7. **`escalation` / aftermath (Scene 7):**
   - Show the absurd new reality caused by the twist.
8. **`outro` (Scene 8):**
   - Punchy final visual gag + short Indonesian comment/tag CTA (*"Tag temen kamu yang..."* or *"Kalau kamu di dunia ini, gimana?"*) designed for loop replays and DM shares.

**Pacing & Narration Density Rule:**
- Write snappy, lively Bahasa Indonesia (~15-20 words per 6s scene, or ~10-13 words per 4s scene) with `tts_rate: "+18%"`, `tts_pitch: "+28Hz"`, `tts_pitch_shift: 1.18`, `fast_cut_sync: true`, `scene_gap_seconds: 0.10`, and `bgm_path: "assets/bgm/in_this_town_bgm.mp3"` (`bgm_volume: 0.16`).
- Every scene MUST change action, camera angle, or expression so the viewer never gets bored.

## 2. Non-Negotiable Technical & Safety Rules

1. **Canonical `@PascalCase` Handles:**
   - Every character and location has a unique `@PascalCase` handle with no spaces or punctuation (e.g., `@Raka`, `@Tono`, `@WarkopMalam`, `@KamarKos`).
   - Every declared character and location for a scene MUST appear explicitly inside that scene's `visual_prompt`.
2. **Zero Em Dashes:**
   - Never use `—` anywhere in `title_id`, `world_rule_id`, `narration_id`, or `visual_prompt`. Use commas, colons, periods, or spaced hyphens (` - `).
3. **Trademark-Safe Visual Prompts:**
   - Never write the raw trademark word `Roblox` in `style_bible`, character/location descriptions, or `visual_prompt`.
   - Always describe the look visually: *"blocky 3D plastic toy avatar, smooth glossy R6/R15 cubic torso and limbs, cylindrical head with simple printed deadpan expression, colorful indie-game lighting"*.
4. **Language Separation:**
   - `narration_id` & `title_id`: Natural casual Indonesian (spoken Gen-Z / daily slang, TTS-friendly punctuation, short punchy sentences).
   - `visual_prompt`, `camera`, `audio_sfx`: Crisp English for maximum Google Flow prompt adherence.
   - Always keep on-screen text disabled in Google Flow (`no text overlays`) so `ffmpeg` burns crisp Indonesian captions afterward.
5. **Storyboard First, Spend Second:**
   - Generate character/location reference stills and the `2x2` storyboard contact sheet first (0 Flow credits).
   - Only run `--spend` video generation after inspecting and approving the storyboard.

## 3. Recommended Google Flow Models (Verified for `gflow-cli`)

- **Image references & storyboard:** `nano-2.1` (Nano Banana 2.1, up to 10 refs, 0 Flow credits) or `nano-pro`.
- **Video generation:** `omni-1.2-flash` (up to 7 reference images, up to 15s) or `veo-lite` (up to 3 reference images, up to 8s).

## 4. Episode YAML Template

Save daily episodes to `episodes/YYYY-MM-DD-epXX-slug.yaml` and validate with:
```powershell
.\.venv\Scripts\python.exe -m roblox_meme_flow.cli validate episodes\<file>.yaml
```

## 5. Bank of 10 Daily Premise Seeds (Bahasa Indonesia)

1. **OTW Anti-Gravitasi:** Di dunia ini, siapa pun yang chat OTW padahal masih rebahan langsung melayang ke langit.
2. **Tinggi Badan = Saldo E-Wallet:** Di dunia ini, tinggi badan kamu otomatis berubah sesuai sisa saldo e-wallet di akhir bulan.
3. **Hutang Bersinar Neon:** Di dunia ini, setiap orang yang belum bayar utang ke temen kepalanya nyala lampu strobo warna hijau.
4. **Kopi Sachet Turbo:** Di dunia ini, minum kopi sachet jam dua pagi bikin langkah kaki kamu langsung speed-hack 10x lebih cepat.
5. **Grup WA Bisu Meledak:** Di dunia ini, kalau kamu cuma read chat grup tanpa bales, HP kamu bakal berubah jadi batu bata raksasa.
6. **AC Kosan Salju:** Di dunia ini, patungan bayar listrik telat sehari bikin kamar kos langsung berubah jadi kutub utara.
7. **Nasi Padang Magnet:** Di dunia ini, bilang "nasi sedikit aja bang" tapi tetap dibungkus segunung bikin gravitasi sekitar kamu berlipat ganda.
8. **Skripsi Boss Fight:** Di dunia ini, setiap dosen bilang "revisi dikit ya", monitor laptop langsung berubah jadi boss monster ber-HP bar merah.
9. **Hujan Lokal Pribadi:** Di dunia ini, tiap kali kamu baru kelar cuci motor, awan hujan mini bakal ngikutin tepat di atas kepala kamu seharian.
10. **Gajian Hilang dalam 3 Detik:** Di dunia ini, uang gajian berbentuk burung emas yang langsung kabur ke kasir minimarket dan paylater begitu masuk rekening.
