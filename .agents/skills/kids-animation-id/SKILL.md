---
name: kids-animation-id
description: Writes cheerful, family-friendly Indonesian 3D animated kids short stories (YouTube Kids, Shorts, TikTok, Reels safe) designed for Google Flow (Nano Banana + Omni 1.2 Flash / Veo Lite) within <= 50 daily Flow credits, with character continuity, vibrant toy/cartoon style, and playful educational payoffs.
---

# Animasi Konten Anak-Anak Indonesia (Kids Animation Skill)

Adapted with continuity standards from `google-flow-scripting` and children's cartoon animation best practices (inspired by open-source skills such as `AKCodez/ai-kids-cartoon-videos` and `lhlGitHub/hand-drawn-storybook-animation-skill`).

Use this Skill whenever `content_mode: "kids_animation_id"` is selected in the Studio UI or CLI.

## 1. Core Formula (Family-Friendly Fast-Paced Kids Shorts, 30-45s)

Default production target fits **80-85 Flow credits/day**: **8 scenes x 6s (`veo-lite`, ~80 credits, ~35-42s after fast-cut)** or **7-9 rapid scenes (`omni-1.2-flash`, 81-84 credits)**, with an optional **Hemat 4x4s (48 credits)** preset when requested. Always set `fast_cut_sync: true` and `scene_gap_seconds: 0.10` so the story flows cheerfully without awkward silent gaps:

1. **`hook` (Scene 1):**
   - Bright, joyful visual surprise right at frame 1 (glowing rainbow cloud, dancing toy animal, giant bouncing candy, friendly blocky robot) + cheerful opening question or magic world rule.
2. **`setup` (Scene 2):**
   - Introduce the cute hero and their joyful world/mission.
3. **`escalation` (Scene 3):**
   - A gentle, funny everyday kids problem appears (lost balloon, wobbly toy tower, sleepy flowers, messy room).
4. **`complication` (Scene 4):**
   - First playful attempt to solve it causes a funny harmless cartoon surprise (bubbles everywhere, bouncing fruit).
5. **`climax` (Scene 5):**
   - Friends team up with kindness, counting, or sharing to try a creative magical solution.
6. **`twist` (Scene 6):**
   - Big colorful magical payoff with sparkles, giggles, and joyful cartoon movement!
7. **`escalation` / celebration (Scene 7):**
   - Everyone celebrates together dancing or playing in the colorful world.
8. **`outro` (Scene 8):**
   - Warm happy lesson + interactive question for kids/parents (*"Warna apa favoritmu? Sebut bareng-bareng yuk!"*) to boost replays.

*(Note: Keep max 2 characters + 1 location per scene when using `veo-lite` to respect its 3-reference-image cap.)*

## 2. Non-Negotiable Kids Safety & Continuity Rules

1. **100% Family-Friendly / YouTube Kids Safe:**
   - Zero violence, scary monsters, bullying, debt/adult slang, sarcasm, or dangerous pranks.
   - Always warm, encouraging, bright daylight or cozy pastel lighting, soft rounded shapes, smiling expressive eyes.
2. **Canonical `@PascalCase` Handles:**
   - Declare every character and location with a unique `@PascalCase` handle (e.g., `@MiloKucing`, `@BobiKelinci`, `@TamanPelangi`).
   - Mention every declared character and location handle explicitly inside every scene's `visual_prompt`.
3. **Zero Em Dashes & Trademark-Safe Visuals:**
   - Never use `—` anywhere in narration or prompts.
   - Never mention raw trademarked franchises (`Roblox`, `Cocomelon`, `Pixar`, `Disney`) in visual prompts; instead describe *"vibrant stylized 3D toy-like cartoon animation, soft glossy rounded playful characters with big friendly eyes, sunny pastel storybook colors, crisp soft global illumination, zero on-screen text"*.
4. **Daily Credit Budget Alignment (80-85 Credits/Day Default, Optional 48-Credit Hemat):**
   - Default to **8 scenes x 6 seconds (`veo-lite`, ~80 credits, ~35-42s after fast-cut)** or **7-9 rapid scenes (`omni-1.2-flash`, 81-84 credits)** for rich 30-45s storytelling, with an optional **4x4s (48 credits)** ultra-saving mode.
5. **Voice & Audio:**
   - Recommended cheerful kids voice preset: `tts_voice: "id-ID-GadisNeural"`, `tts_rate: "+12%"`, `tts_pitch: "+24Hz"`, `tts_pitch_shift: 1.12`, `fast_cut_sync: true`, `scene_gap_seconds: 0.10`.
   - Always pair with cheerful light BGM (`bgm_path: "assets/bgm/in_this_town_bgm.mp3"`, `bgm_volume: 0.16`) and playful cartoon SFX (pops, sparkles, giggles).

## 3. Bank of 10 Indonesian Kids Animation Episode Seeds

1. **Awan Pelangi Milo:** Di dunia awan warna-warni, kucing kecil Milo membagikan tetes pelangi supaya kebun teman-temannya kembali mekar.
2. **Balon Angka Kelinci:** Kelinci kecil Bobi mengejar tiga balon warna merah, kuning, dan biru sambil mengajak anak-anak berhitung bersama.
3. **Robot Sikat Gigi:** Robot mini Bibo yang awalnya malas sikat gigi berubah jadi berkilau seperti bintang setelah belajar sikat gigi pagi.
4. **Hujan Permen Buah:** Saat hujan buah stroberi dan jeruk turun di taman, anak-anak mainan bekerja sama membuat payung daun raksasa.
5. **Bebek Kuning Berbagi:** Bebek kuning Kiki menemukan kue besar dan membaginya dengan tupai, kelinci, dan kura-kura hingga semua menari.
6. **Kereta Warna-Warni:** Kereta mainan kecil mengantar buah-buahan ke stasiun warna yang tepat (merah untuk apel, kuning untuk pisang).
7. **Kura-Kura Roket Gelembung:** Kura-kura lambat Tutu memakai gelembung sabun ajaib untuk membantu burung kecil kembali ke sarangnya.
8. **Bintang Tidur Siang:** Bulan tersenyum mengajak bintang-bintang kecil merapikan mainan sebelum tidur dengan nyanyian lembut.
9. **Kupu-Kupu Pelukis:** Kupu-kupu ajaib mengecat taman yang abu-abu menjadi penuh bunga warna-warni setiap kali ada yang bilang terima kasih.
10. **Dino Kecil Suka Sayur:** Dinosaurus mini hijau yang tadinya takut wortel malah jadi bisa melompat super tinggi setelah mencoba satu gigitan.
