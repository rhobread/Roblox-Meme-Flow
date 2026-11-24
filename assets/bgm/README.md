# Background Music (BGM) Assets

Default BGM track for `"In This World"` Roblox meme videos:
- Source: `https://www.youtube.com/watch?v=hmrcPwb7rxE` ("In this town roblox background music")
- Local file (ignored by Git to avoid committing third-party audio): `assets/bgm/in_this_town_bgm.mp3`

To re-download locally if missing on a fresh clone:
```powershell
$ffmpeg = .\.venv\Scripts\python.exe -c "from roblox_meme_flow.audio_video import find_ffmpeg; print(find_ffmpeg())"
.\.venv\Scripts\yt-dlp.exe -x --audio-format mp3 --audio-quality 0 --ffmpeg-location $ffmpeg -o "assets\bgm\in_this_town_bgm.%(ext)s" "https://www.youtube.com/watch?v=hmrcPwb7rxE"
```
