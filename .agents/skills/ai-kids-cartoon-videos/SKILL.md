---
name: ai-kids-cartoon-videos
description: Generate complete animated nursery-rhyme kids videos end to end (an original character, a catchy sing-along song, and scene-by-scene animation) by driving Higgsfield through its MCP inside Claude. Use to build and scale a faceless YouTube Kids channel. Triggers on "make a kids video", "nursery rhyme video", "animated kids cartoon", "faceless kids channel", "YouTube Kids automation".
---

# AI Kids Cartoon Videos (Claude + Higgsfield MCP)

Turn one idea into a finished, ready-to-post animated kids video: an original sing-along character, a catchy nursery rhyme, and a full set of bright 3D scenes, generated start to finish by Claude driving Higgsfield through the MCP. Built for faceless YouTube Kids channels you can post to every single day.

**Why this works:** kids channels pull hundreds of thousands of views per video, and YouTube pays roughly $200 to $3,000 per 100,000 views. One repeatable character plus a daily upload is a channel that compounds. You never show your face and you never animate a single frame by hand.

**Heads up, do this the right way:** this builds ORIGINAL characters and songs. Do not copy real, trademarked characters, names, or songs from existing kids brands. Read the "Safety and policy" section before you post a single video.

## One-time setup (about 2 minutes, no code)

1. Open Claude at claude.ai, go to **Settings, then Connectors, then Add custom connector**.
2. Go to **higgsfield.ai/mcp** and copy the MCP link.
3. Paste it into Claude, name the connector **Higgsfield**, and save. Higgsfield is now wired into Claude.
4. Start a chat and confirm Claude can see the Higgsfield tools (image and video generation). Use the **Seedance 2.0** model for the cartoon look.

Then paste this whole file into a Claude Project (or as custom instructions) and kick it off with the Master Prompt below.

## The formula (the look and feel that actually holds a toddler's attention)

Every scene has to hit these or retention falls off a cliff:

- **Aesthetic:** bright, glossy **3D cartoon**, soft rounded shapes, thick clean outlines, primary and candy colors, soft even lighting, simple uncluttered backgrounds.
- **Character:** one hero, **huge expressive eyes**, oversized head, tiny body, permanently cheerful. Baby animals or toddler-coded characters land best.
- **Song:** one short, repetitive, **sing-along** rhyme. Simple words, a hook repeated three or more times, call and response, roughly 60 to 110 BPM.
- **Micro-lesson:** teach ONE tiny thing per video, a color, a number, an animal sound, sharing, brushing teeth, bedtime.
- **Pacing:** a new visual every 2 to 4 seconds, lots of bounce, exaggerated happy reactions.
- **Length:** 2 to 4 minutes (loop the song two or three times), gentle and safe the whole way through.

## The workflow: idea to finished video

### Step 1, pick the theme and song
Ask Claude to brainstorm ten ideas, each one an original character plus one micro-lesson plus a one-line song hook. Pick the one you like.

### Step 2, lock the character FIRST (the single biggest quality lever)
Consistency is everything in a kids series. Before any scenes, generate a **character sheet**: the same character from the front, the side, and three-quarter view, with a fixed name, color palette, and outfit. Save those images and reuse them as the reference on every later scene. Character drift is what makes a channel look cheap.

### Step 3, write the song and the storyboard
Have Claude write the full lyrics (a verse plus a chorus repeated three times), then a **scene-by-scene storyboard**, one line per 2 to 4 second beat: what the character does, the background, and the lyric playing over it.

### Step 4, generate the scenes
For each storyboard beat, have Claude prompt Higgsfield with the scene action plus the fixed **Style Block** (below) plus the character reference. Generate them in order, and keep the same Style Block on every shot.

### Step 5, add the song and stitch
Generate or drop in the song, lay the scenes in storyboard order, and sync the action to the beat. Export 16:9 for YouTube, and optionally a 9:16 cut for Shorts.

### Step 6, package for YouTube Kids
Write the title, design the thumbnail, write the description, add tags, and put it in a playlist. Set **"Made for Kids"** on the upload (required). See the optimization section.

### Step 7, batch and post daily
Reuse the same hero character across videos, that recurring character IS your show. Generate a week at a time, post once a day at the same time. Consistency and volume are the whole game.

## Copy-paste prompts

### Master prompt (start here)

```
You are my kids-cartoon video producer, with Higgsfield connected through the MCP.
Goal: produce one finished, original, wholesome animated nursery-rhyme video for a faceless YouTube Kids channel.

Work through this in order and pause for my OK between steps:
1. Pitch 10 ideas. Each is one ORIGINAL character (never an existing brand's), one micro-lesson, one song hook.
2. Once I pick one: generate a character sheet (front, side, three-quarter) and lock the name and color palette.
3. Write the song (a verse plus a chorus repeated 3 times) and a scene-by-scene storyboard (one 2 to 4 second beat per line).
4. Generate every scene with Higgsfield using the Style Block plus the character reference, in order.
5. Give me the title, a thumbnail concept, the description, 15 tags, and a playlist name.
Keep everything bright, gentle, safe, and original. Never reproduce real trademarked characters or songs.
```

### Style Block (paste this into EVERY scene prompt, word for word)

```
bright glossy 3D cartoon, soft rounded shapes, thick clean outlines, big expressive eyes,
primary and candy colors, soft even studio lighting, simple uncluttered background,
cheerful wholesome toddler aesthetic, smooth bouncy motion, high detail, 16:9
```

### Character-sheet prompt

```
Create a character reference sheet for [NAME], an original kids-cartoon [animal or character]:
front, side, and three-quarter views, neutral pose, consistent [colors and outfit]. [paste the Style Block]
```

### Scene prompt template

```
Scene [n]: [character] [action] in [simple background], expression [happy / surprised / giggling],
matching the lyric "[lyric line]". Keep [NAME] exactly on-model from the reference. [paste the Style Block]
```

## Consistency tricks (what separates a real channel from AI slop)

- Pass the **character sheet** as a reference on every single scene.
- Keep the **Style Block identical** on every shot. Do not paraphrase it.
- If Higgsfield exposes a **seed**, lock it and reuse it across the whole series.
- Same character, same palette, same thumbnail font, that is your brand.
- Generate scenes **in order** so the character and the energy stay continuous.

## YouTube Kids optimization

- **Title:** the lesson plus the character, kept simple, for example "Learn Colors with Bibi the Bunny".
- **Thumbnail:** the character mid-smile, one or two huge words, bright background.
- **Tags:** nursery rhymes, kids songs, learn colors, learn numbers, baby songs, toddler learning, plus your character name.
- **Playlists:** group by theme (Colors, Numbers, Animals). Playlists drive autoplay and watch-time.
- **Cadence:** one video a day at the same time. Consistency trains the algorithm.
- **Required:** mark every upload **"Made for Kids."**

## Safety and policy (read this before posting)

Kids content is heavily regulated. Protect yourself:

- **Original only.** Build your own characters, names, and songs. Do not recreate, imitate, or borrow trademarked characters, names, or songs from existing kids channels. That is trademark and copyright infringement.
- **"Made for Kids" is mandatory** on every upload (COPPA). Note that it disables some features such as comments and personalized ads.
- **Keep it wholesome.** No scary, violent, weird, or disturbing content, ever. Gentle and safe every second. Low-quality or creepy kids content gets channels removed.
- **No data collection from children** and no external links aimed at kids.
- Higgsfield and YouTube each have their own terms. Stay inside both.

## Scale it

- Turn your hero into a **series**: same character, a new lesson every day.
- Spin a **second channel** in another language by re-voicing the same videos.
- Build a **back catalog**: thirty videos across thirty themes, then let the library earn while you keep posting.
- Once the channel is monetized, the daily twenty-minute batch is the entire job.

---

Built by [@ariacodez](https://instagram.com/ariacodez). Now go make something kids actually love.
