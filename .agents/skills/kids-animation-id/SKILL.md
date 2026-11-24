---
name: kids-animation-id
description: Writes cheerful, family-friendly Indonesian 3D animated kids short stories (YouTube Kids, Shorts, TikTok, Reels safe) designed for Google Flow (Nano Banana + Omni 1.2 Flash / Veo Lite) within <= 50 daily Flow credits, with character continuity, vibrant toy/cartoon style, and playful educational payoffs.
---

# Animasi Konten Anak-Anak Indonesia (Kids Animation Skill)

Adapted with continuity standards from `google-flow-scripting` and children's cartoon animation best practices (inspired by open-source skills such as `AKCodez/ai-kids-cartoon-videos` and `lhlGitHub/hand-drawn-storybook-animation-skill`).

Use this Skill whenever `content_mode: "kids_animation_id"` is selected in the Studio UI or CLI.

## 1. Core Formula (Family-Friendly Viral Kids Shorts, 16-20s)

Designed specifically to fit **<= 50 Flow credits/day** (default **4 scenes x 4 seconds = 16 seconds = 48 credits** on `omni-1.2-flash`) while maximizing YouTube Kids / Shorts / Reels watch time and replays:

1. **`hook` (Scene 1, 4s):**
   - Bright, joyful visual surprise right at frame 1 (a glowing rainbow cloud, dancing toy animal, giant bouncing candy, friendly blocky robot).
   - Cheerful opening question or magic world rule in warm Indonesian: *"Di dunia awan warna-warni, ada kucing kecil yang suka berbagi pelangi!"*
2. **`escalation` (Scene 2, 4s):**
   - A gentle, funny everyday kids problem (a friend drops a balloon, a toy tower wobbles, a bunny forgets to brush its teeth, a rainy puddle blocks the playground).
3. **`twist` (Scene 3, 4s):**
   - Playful magical/creative solution with big expressive cartoon reactions, sparkles, giggles, and colorful motion.
4. **`outro` (Scene 4, 4s):**
   - Warm happy ending + interactive question for kids/parents (*"Warna apa favoritmu? Sebut bareng-bareng yuk!"* or *"Jangan lupa berbagi sama teman ya!"*) to trigger replays and engagement.

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
4. **Daily Credit Budget Alignment (<= 50 Credits/Day):**
   - Default to **4 scenes x 4 seconds** (`16s` total, `omni-1.2-flash`, ~48 credits total) or **3 scenes x 5 seconds** (`15s` total, ~45 credits total) so 1 full episode per day is 100% sustainable on Google Flow's +50 daily credit refill.
5. **Voice & Audio:**
   - Recommended cheerful kids voice preset: `tts_voice: "id-ID-GadisNeural"`, `tts_rate: "+10%"`, `tts_pitch: "+24Hz"`, `tts_pitch_shift: 1.12`.
   - Always pair with cheerful light BGM (`bgm_volume: 0.16`) and playful cartoon SFX (pops, sparkles, giggles).

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
