from __future__ import annotations

import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from roblox_meme_flow.audio_video import assemble_video, generate_voiceover_and_srt
from roblox_meme_flow.credit_guard import (
    BUDGET_PRESETS,
    check_render_budget,
    estimate_episode_credits,
    get_day_stats,
    get_policy,
    update_policy,
)
from roblox_meme_flow.flow_runner import get_live_flow_credits, write_and_optionally_run_flow
from roblox_meme_flow.layout import EpisodeLayout
from roblox_meme_flow.models import load_episode
from roblox_meme_flow.prompt_builder import export_plan
from roblox_meme_flow.researcher import build_viral_research_brief
from roblox_meme_flow.script_gen import (
    AI_ENGINES,
    VOICE_PRESETS,
    build_t3_generation_prompt,
    generate_script_via_antigravity,
    generate_script_via_kilo,
    validate_and_save_yaml,
)
from roblox_meme_flow.validator import has_errors, validate_episode

STATIC_DIR = Path(__file__).resolve().parent / "static"


@dataclass
class JobState:
    job_id: str
    kind: str
    status: Literal["running", "done", "error"] = "running"
    logs: list[str] = field(default_factory=list)
    result: dict[str, object] | None = None
    error: str | None = None

    def append(self, message: str) -> None:
        self.logs.append(message)


class SettingsPayload(BaseModel):
    daily_credit_limit: int = 85
    max_videos_per_day: int = 1
    daily_refill_credits: int = 50


class ResearchPayload(BaseModel):
    content_mode: Literal["meme_roblox_id", "kids_animation_id"] = "meme_roblox_id"
    budget_preset: str = "long_veo_80"
    voice_preset: str = "preset_a"
    topic_hint: str = ""
    bgm_path: str = "assets/bgm/in_this_town_bgm.mp3"
    fetch_live: bool = True


class GenerateScriptPayload(ResearchPayload):
    engine: Literal["kilo_free", "kilo_custom", "antigravity"] = "kilo_free"
    model: str = "kilo/kilo-auto/free"


class SaveEpisodePayload(BaseModel):
    yaml_text: str
    filename: str | None = None


class SimpleUpdateEpisodePayload(BaseModel):
    title_id: str | None = None
    voice_preset: str | None = None
    bgm_path: str | None = None
    bgm_volume: float | None = None
    enable_subtitles: bool | None = None
    fast_cut_sync: bool | None = None
    narrations: list[str] | None = None


class EpisodeJobPayload(BaseModel):
    filename: str
    override_limit: bool = False
    voice_preset: str | None = None
    bgm_path: str | None = None
    bgm_volume: float | None = None
    enable_subtitles: bool | None = None
    fast_cut_sync: bool | None = None


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _safe_resolve_under(base: Path, rel: str) -> Path:
    resolved = (base / rel).resolve()
    base_resolved = base.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Path outside allowed directory") from exc
    return resolved


def create_app(project_root: Path | None = None) -> FastAPI:
    root = (project_root or Path.cwd()).resolve()
    episodes_dir = root / "episodes"
    outputs_dir = root / "outputs"
    bgm_dir = root / "assets" / "bgm"
    ledger_path = outputs_dir / "credit_ledger.json"

    app = FastAPI(title="Roblox-Meme-Flow Studio", version="0.2.0")
    jobs: dict[str, JobState] = {}
    jobs_lock = threading.Lock()
    lifecycle_lock = threading.Lock()
    now_mono = time.monotonic()
    lifecycle_state: dict[str, float | None] = {
        "started_at": now_mono,
        "last_heartbeat": now_mono,
        "ui_closed_at": None,
    }

    def _touch_heartbeat() -> None:
        with lifecycle_lock:
            lifecycle_state["last_heartbeat"] = time.monotonic()
            lifecycle_state["ui_closed_at"] = None

    def _mark_ui_closing() -> None:
        with lifecycle_lock:
            lifecycle_state["ui_closed_at"] = time.monotonic()

    def _has_running_jobs() -> bool:
        with jobs_lock:
            return any(j.status == "running" for j in jobs.values())

    def _lifecycle_snapshot() -> dict[str, object]:
        with lifecycle_lock:
            snap = dict(lifecycle_state)
        return {
            "started_at": snap["started_at"],
            "last_heartbeat": snap["last_heartbeat"],
            "ui_closed_at": snap["ui_closed_at"],
            "has_running_jobs": _has_running_jobs(),
        }

    app.state.lifecycle_snapshot = _lifecycle_snapshot
    app.state.has_running_jobs = _has_running_jobs

    def _start_job(kind: str, fn) -> str:
        job_id = uuid.uuid4().hex[:10]
        state = JobState(job_id=job_id, kind=kind)
        with jobs_lock:
            jobs[job_id] = state

        def _runner() -> None:
            try:
                res = fn(state)
                state.result = res
                state.status = "done"
            except Exception as exc:
                state.error = str(exc)
                state.append(f"[ERROR] {exc}")
                state.status = "error"

        threading.Thread(target=_runner, daemon=True).start()
        return job_id

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        _touch_heartbeat()
        html_path = STATIC_DIR / "index.html"
        return HTMLResponse(
            html_path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    @app.post("/api/heartbeat")
    def api_heartbeat() -> dict[str, object]:
        _touch_heartbeat()
        return {"ok": True, "has_running_jobs": _has_running_jobs()}

    @app.post("/api/ui-closing")
    def api_ui_closing() -> dict[str, object]:
        _mark_ui_closing()
        return {"ok": True}

    @app.get("/api/status")
    def api_status(refresh_credits: bool = False) -> dict[str, object]:
        policy = get_policy(ledger_path)
        day = get_day_stats(ledger_path)
        live_credits = get_live_flow_credits() if refresh_credits else None
        bgm_files = (
            [f"assets/bgm/{p.name}" for p in sorted(bgm_dir.glob("*.mp3"))]
            if bgm_dir.exists()
            else []
        )
        skills_dir = root / ".agents" / "skills"
        skills = (
            sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
            if skills_dir.exists()
            else []
        )
        return {
            "project_root": str(root),
            "live_credits": live_credits,
            "policy": {
                "daily_credit_limit": policy.daily_credit_limit,
                "max_videos_per_day": policy.max_videos_per_day,
                "daily_refill_credits": policy.daily_refill_credits,
            },
            "today": day,
            "bgm_files": bgm_files,
            "voice_presets": VOICE_PRESETS,
            "budget_presets": BUDGET_PRESETS,
            "ai_engines": AI_ENGINES,
            "skills": skills,
        }

    @app.post("/api/settings")
    def api_update_settings(payload: SettingsPayload) -> dict[str, object]:
        pol = update_policy(
            ledger_path,
            daily_credit_limit=payload.daily_credit_limit,
            max_videos_per_day=payload.max_videos_per_day,
            daily_refill_credits=payload.daily_refill_credits,
        )
        return {
            "daily_credit_limit": pol.daily_credit_limit,
            "max_videos_per_day": pol.max_videos_per_day,
            "daily_refill_credits": pol.daily_refill_credits,
        }

    @app.get("/api/episodes")
    def api_list_episodes() -> dict[str, object]:
        import datetime as _dt

        items: list[dict[str, object]] = []
        if episodes_dir.exists():
            for path in sorted(episodes_dir.glob("*.yaml")):
                stat = path.stat()
                created_ts = stat.st_ctime
                updated_ts = stat.st_mtime
                created_iso = _dt.datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M")
                try:
                    ep = load_episode(path)
                    issues = validate_episode(ep)
                    layout = EpisodeLayout.for_episode(outputs_dir, ep.episode_id)
                    est = estimate_episode_credits(ep)
                    budget = check_render_budget(ep, ledger_path)
                    refs = sorted(layout.refs_dir.glob("*.*")) if layout.refs_dir.exists() else []
                    clips = sorted(layout.clips_dir.glob("scene_*.mp4")) if layout.clips_dir.exists() else []
                    size_bytes = path.stat().st_size + _dir_size_bytes(layout.root)
                    items.append(
                        {
                            "filename": path.name,
                            "episode_id": ep.episode_id,
                            "title_id": ep.title_id,
                            "content_mode": ep.content_mode,
                            "duration_seconds": ep.total_duration_seconds,
                            "scene_count": len(ep.scenes),
                            "video_model": ep.video_model,
                            "estimated_credits": est,
                            "fits_daily_budget": budget.allowed,
                            "valid": not has_errors(issues),
                            "issue_count": len(issues),
                            "has_refs": len(refs) > 0,
                            "has_storyboard": (layout.images_dir / "storyboard.jpg").exists(),
                            "has_voiceover": (layout.audio_dir / "voiceover.mp3").exists(),
                            "clip_count": len(clips),
                            "has_final_video": (layout.final_dir / "final_9x16.mp4").exists(),
                            "disk_size_mb": round(size_bytes / (1024 * 1024), 2),
                            "created_ts": created_ts,
                            "updated_ts": updated_ts,
                            "created_label": created_iso,
                        }
                    )
                except Exception as exc:
                    items.append(
                        {
                            "filename": path.name,
                            "valid": False,
                            "error": str(exc),
                            "created_ts": created_ts,
                            "updated_ts": updated_ts,
                            "created_label": created_iso,
                        }
                    )
        items.sort(key=lambda x: float(x.get("created_ts", 0)), reverse=True)
        return {"episodes": items}

    @app.get("/api/episodes/{filename}")
    def api_get_episode(filename: str) -> dict[str, object]:
        ep_path = _safe_resolve_under(episodes_dir, filename)
        if not ep_path.exists():
            raise HTTPException(status_code=404, detail="Episode tidak ditemukan")
        yaml_text = ep_path.read_text(encoding="utf-8")
        ep = load_episode(ep_path)
        issues = validate_episode(ep)
        layout = EpisodeLayout.for_episode(outputs_dir, ep.episode_id)
        budget = check_render_budget(ep, ledger_path)

        def _rel_media(p: Path) -> str | None:
            if not p.exists():
                return None
            return "/media/outputs/" + p.resolve().relative_to(outputs_dir.resolve()).as_posix()

        refs_urls = (
            [
                {"name": p.name, "url": _rel_media(p)}
                for p in sorted(layout.refs_dir.glob("*.*"))
            ]
            if layout.refs_dir.exists()
            else []
        )
        clips_urls = (
            [
                {"name": p.name, "url": _rel_media(p)}
                for p in sorted(layout.clips_dir.glob("scene_*.mp4"))
            ]
            if layout.clips_dir.exists()
            else []
        )

        return {
            "filename": ep_path.name,
            "yaml_text": yaml_text,
            "episode": ep.model_dump(),
            "estimated_credits": estimate_episode_credits(ep),
            "budget": budget.to_dict(),
            "disk_size_mb": round((ep_path.stat().st_size + _dir_size_bytes(layout.root)) / (1024 * 1024), 2),
            "issues": [{"severity": i.severity, "code": i.code, "message": i.message} for i in issues],
            "assets": {
                "folder": str(layout.root),
                "refs": refs_urls,
                "storyboard_url": _rel_media(layout.images_dir / "storyboard.jpg"),
                "voiceover_url": _rel_media(layout.audio_dir / "voiceover.mp3"),
                "clips": clips_urls,
                "final_video_url": _rel_media(layout.final_dir / "final_9x16.mp4"),
            },
        }

    @app.post("/api/episodes/save")
    def api_save_episode(payload: SaveEpisodePayload) -> dict[str, object]:
        try:
            saved = validate_and_save_yaml(payload.yaml_text, episodes_dir, payload.filename)
            return {"ok": True, **saved}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/episodes/{filename}/update-simple")
    def api_update_simple(filename: str, payload: SimpleUpdateEpisodePayload) -> dict[str, object]:
        import yaml as _yaml

        ep_path = _safe_resolve_under(episodes_dir, filename)
        if not ep_path.exists():
            raise HTTPException(status_code=404, detail="Episode tidak ditemukan")
        raw = _yaml.safe_load(ep_path.read_text(encoding="utf-8"))
        if payload.title_id:
            raw["title_id"] = payload.title_id.strip()
        if payload.voice_preset and payload.voice_preset in VOICE_PRESETS:
            vp = VOICE_PRESETS[payload.voice_preset]
            raw["tts_voice"] = vp["tts_voice"]
            raw["tts_rate"] = vp["tts_rate"]
            raw["tts_pitch"] = vp["tts_pitch"]
            raw["tts_pitch_shift"] = vp["tts_pitch_shift"]
        if payload.bgm_path is not None:
            raw["bgm_path"] = payload.bgm_path or None
        if payload.bgm_volume is not None:
            raw["bgm_volume"] = float(payload.bgm_volume)
        if payload.enable_subtitles is not None:
            raw["enable_subtitles"] = bool(payload.enable_subtitles)
        if payload.fast_cut_sync is not None:
            raw["fast_cut_sync"] = bool(payload.fast_cut_sync)
        if payload.narrations and isinstance(raw.get("scenes"), list):
            for idx, text in enumerate(payload.narrations):
                if idx < len(raw["scenes"]) and text.strip():
                    raw["scenes"][idx]["narration_id"] = text.strip()

        dumped = _yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
        try:
            saved = validate_and_save_yaml(dumped, episodes_dir, ep_path.name)
            return {"ok": True, **saved}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/episodes/{filename}")
    def api_delete_episode(filename: str) -> dict[str, object]:
        ep_path = _safe_resolve_under(episodes_dir, filename)
        if not ep_path.exists():
            raise HTTPException(status_code=404, detail="Episode tidak ditemukan")

        episode_id: str | None = None
        try:
            ep = load_episode(ep_path)
            episode_id = ep.episode_id
        except Exception:
            pass

        freed_bytes = ep_path.stat().st_size
        deleted_output_dir: str | None = None

        if episode_id:
            ep_out = _safe_resolve_under(outputs_dir, episode_id)
            if ep_out.exists() and ep_out.is_dir():
                freed_bytes += _dir_size_bytes(ep_out)
                shutil.rmtree(ep_out)
                deleted_output_dir = str(ep_out)

        ep_path.unlink(missing_ok=True)
        return {
            "ok": True,
            "deleted_filename": ep_path.name,
            "episode_id": episode_id,
            "deleted_output_dir": deleted_output_dir,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        }

    @app.post("/api/research")
    def api_research(payload: ResearchPayload) -> dict[str, object]:
        prompt, brief = build_t3_generation_prompt(
            project_root=root,
            content_mode=payload.content_mode,
            budget_preset=payload.budget_preset,
            voice_preset=payload.voice_preset,
            topic_hint=payload.topic_hint,
            bgm_path=payload.bgm_path,
        )
        return {
            "brief": brief.to_dict(),
            "t3_prompt": prompt,
        }

    @app.post("/api/generate-script")
    def api_generate_script(payload: GenerateScriptPayload) -> dict[str, object]:
        def _work(job: JobState) -> dict[str, object]:
            job.append("[1/3] Mengambil tren viral Indonesia hari ini...")
            prompt, brief = build_t3_generation_prompt(
                project_root=root,
                content_mode=payload.content_mode,
                budget_preset=payload.budget_preset,
                voice_preset=payload.voice_preset,
                topic_hint=payload.topic_hint,
                bgm_path=payload.bgm_path,
            )
            job.append(f"      Siap! Ditemukan {len(brief.live_trends_id)} topik tren Indonesia.")
            if payload.engine == "antigravity":
                job.append(f"[2/3] AI sedang menulis script ({payload.model})...")
                saved = generate_script_via_antigravity(
                    root, prompt, model=payload.model, log_callback=job.append
                )
            else:
                model_name = payload.model.strip() or "kilo/kilo-auto/free"
                job.append(f"[2/3] AI sedang menulis cerita & scene ({model_name})...")
                saved = generate_script_via_kilo(
                    root, prompt, model=model_name, log_callback=job.append
                )
            job.append(f"[3/3] Selesai! Episode tersimpan: {saved['title_id']}")
            return {"saved": saved, "brief": brief.to_dict()}

        return {"job_id": _start_job("generate_script", _work)}

    def _apply_audio_overrides(ep, payload: EpisodeJobPayload):
        if payload.voice_preset and payload.voice_preset in VOICE_PRESETS:
            vp = VOICE_PRESETS[payload.voice_preset]
            ep.tts_voice = str(vp["tts_voice"])
            ep.tts_rate = str(vp["tts_rate"])
            ep.tts_pitch = str(vp["tts_pitch"])
            ep.tts_pitch_shift = float(vp["tts_pitch_shift"])
        if payload.bgm_path is not None:
            ep.bgm_path = payload.bgm_path or None
        if payload.bgm_volume is not None:
            ep.bgm_volume = float(payload.bgm_volume)
        if payload.enable_subtitles is not None:
            ep.enable_subtitles = bool(payload.enable_subtitles)
        if payload.fast_cut_sync is not None:
            ep.fast_cut_sync = bool(payload.fast_cut_sync)
        return ep

    @app.post("/api/jobs/preview")
    def api_job_preview(payload: EpisodeJobPayload) -> dict[str, object]:
        ep_path = _safe_resolve_under(episodes_dir, payload.filename)
        if not ep_path.exists():
            raise HTTPException(status_code=404, detail="Episode tidak ditemukan")

        def _work(job: JobState) -> dict[str, object]:
            ep = _apply_audio_overrides(load_episode(ep_path), payload)
            issues = validate_episode(ep)
            if has_errors(issues):
                raise RuntimeError("Validasi gagal: " + "; ".join(i.message for i in issues))
            job.append("[1/3] Export plan & subtitle SRT ke struktur folder rapi...")
            export_plan(ep, outputs_dir, source_yaml=ep_path)
            job.append("[2/3] Generate Voiceover Bahasa Indonesia...")
            generate_voiceover_and_srt(ep, outputs_dir)
            job.append("[3/3] Generate gambar referensi & storyboard di Google Flow (0 kredit)...")
            write_and_optionally_run_flow(
                ep=ep,
                out_dir=outputs_dir,
                spend=False,
                execute=True,
                stages={"reference_image", "storyboard"},
                log_callback=job.append,
            )
            job.append("[SELESAI - 0 KREDIT] Preview siap dicek!")
            return {"episode_id": ep.episode_id, "filename": ep_path.name}

        return {"job_id": _start_job("preview", _work)}

    @app.post("/api/jobs/render")
    def api_job_render(payload: EpisodeJobPayload) -> dict[str, object]:
        ep_path = _safe_resolve_under(episodes_dir, payload.filename)
        if not ep_path.exists():
            raise HTTPException(status_code=404, detail="Episode tidak ditemukan")

        def _work(job: JobState) -> dict[str, object]:
            ep = _apply_audio_overrides(load_episode(ep_path), payload)
            layout = EpisodeLayout.for_episode(outputs_dir, ep.episode_id)
            layout.ensure_dirs()
            existing_refs = list(layout.refs_dir.glob("*.*")) if layout.refs_dir.exists() else []
            if not existing_refs:
                job.append("[0/3] Gambar referensi belum ada — membuat gambar karakter & lokasi dulu (0 kredit)...")
                export_plan(ep, outputs_dir, source_yaml=ep_path)
                write_and_optionally_run_flow(
                    ep=ep,
                    out_dir=outputs_dir,
                    spend=False,
                    execute=True,
                    stages={"reference_image"},
                    log_callback=job.append,
                )
            job.append("[1/3] Memeriksa limit kredit harian & menjalankan Google Flow Video...")
            write_and_optionally_run_flow(
                ep=ep,
                out_dir=outputs_dir,
                spend=True,
                execute=True,
                stages={"video_scene"},
                override_limit=payload.override_limit,
                log_callback=job.append,
            )
            if not (layout.audio_dir / "voiceover.mp3").exists():
                job.append("[2/3] Generate Voiceover Bahasa Indonesia...")
                generate_voiceover_and_srt(ep, outputs_dir)
            clips = sorted(layout.clips_dir.glob("scene_*.mp4"))
            if not clips:
                raise RuntimeError(f"Tidak ada klip scene_*.mp4 di {layout.clips_dir}")
            job.append(f"[3/3] Menggabungkan {len(clips)} klip + VO + BGM + Subtitle...")
            bgm_resolved = (root / ep.bgm_path) if ep.bgm_path else None
            out_mp4 = assemble_video(
                ep=ep,
                clips=clips,
                out_dir=outputs_dir,
                voiceover_path=layout.audio_dir / "voiceover.mp3",
                srt_path=layout.subtitles_dir / "captions.srt",
                bgm_path=bgm_resolved if (bgm_resolved and bgm_resolved.exists()) else None,
            )
            job.append(f"[VIDEO SIAP UPLOAD] {out_mp4}")
            return {"episode_id": ep.episode_id, "final_video": str(out_mp4)}

        return {"job_id": _start_job("render", _work)}

    @app.post("/api/jobs/revoice")
    def api_job_revoice(payload: EpisodeJobPayload) -> dict[str, object]:
        ep_path = _safe_resolve_under(episodes_dir, payload.filename)
        if not ep_path.exists():
            raise HTTPException(status_code=404, detail="Episode tidak ditemukan")

        def _work(job: JobState) -> dict[str, object]:
            ep = _apply_audio_overrides(load_episode(ep_path), payload)
            layout = EpisodeLayout.for_episode(outputs_dir, ep.episode_id)
            clips = sorted(layout.clips_dir.glob("scene_*.mp4"))
            job.append("[1/2] Membuat ulang Voiceover & Subtitle (0 kredit)...")
            generate_voiceover_and_srt(ep, outputs_dir)
            if not clips:
                job.append(
                    "[SELESAI - 0 KREDIT] Suara preview diperbarui! "
                    "BGM & subtitle akan otomatis terpasang saat klik Render Video."
                )
                return {"episode_id": ep.episode_id, "voiceover_only": True}
            job.append("[2/2] Mixing ulang klip + VO baru + BGM + Subtitle (0 kredit)...")
            bgm_resolved = (root / ep.bgm_path) if ep.bgm_path else None
            out_mp4 = assemble_video(
                ep=ep,
                clips=clips,
                out_dir=outputs_dir,
                voiceover_path=layout.audio_dir / "voiceover.mp3",
                srt_path=layout.subtitles_dir / "captions.srt",
                bgm_path=bgm_resolved if (bgm_resolved and bgm_resolved.exists()) else None,
            )
            job.append(f"[SELESAI - 0 KREDIT] {out_mp4}")
            return {"episode_id": ep.episode_id, "final_video": str(out_mp4)}

        return {"job_id": _start_job("revoice", _work)}

    @app.get("/api/jobs/{job_id}")
    def api_job_status(job_id: str) -> dict[str, object]:
        with jobs_lock:
            state = jobs.get(job_id)
        if not state:
            raise HTTPException(status_code=404, detail="Job tidak ditemukan")
        return {
            "job_id": state.job_id,
            "kind": state.kind,
            "status": state.status,
            "logs": state.logs,
            "result": state.result,
            "error": state.error,
        }

    @app.post("/api/episodes/{filename}/open-folder")
    def api_open_folder(filename: str) -> dict[str, object]:
        ep_path = _safe_resolve_under(episodes_dir, filename)
        ep = load_episode(ep_path)
        layout = EpisodeLayout.for_episode(outputs_dir, ep.episode_id)
        layout.ensure_dirs()
        subprocess.Popen(["explorer.exe", str(layout.root)])
        return {"ok": True, "folder": str(layout.root)}

    @app.get("/media/outputs/{subpath:path}")
    def serve_output_media(subpath: str) -> FileResponse:
        target = _safe_resolve_under(outputs_dir, subpath)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File tidak ditemukan")
        return FileResponse(target)

    @app.get("/media/bgm/{filename}")
    def serve_bgm_media(filename: str) -> FileResponse:
        target = _safe_resolve_under(bgm_dir, filename)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="BGM tidak ditemukan")
        return FileResponse(target)

    return app
