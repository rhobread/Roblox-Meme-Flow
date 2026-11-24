from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from roblox_meme_flow.models import EpisodeSpec

JAKARTA_TZ = dt.timezone(dt.timedelta(hours=7), "WIB")

# Empirically verified on Google Flow (2026-11-24):
# omni-1.2-flash = 3 credits/second (e.g., 4s=12 cr, 5s=15 cr, 6s=18 cr)
CREDITS_PER_SECOND_BY_MODEL: dict[str, int] = {
    "omni-1.2-flash": 3,
    "omni-1.2": 3,
    "omni-flash": 3,
}

FLAT_CREDITS_PER_CLIP_BY_MODEL: dict[str, int] = {
    "veo-lite": 10,
    "veo-lite-lp": 10,
    "veo-fast": 20,
    "veo-quality": 50,
}

BUDGET_PRESETS: dict[str, dict[str, object]] = {
    "hemat_50": {
        "label": "Hemat 1 Video/Hari Selamanya (4x4s = 48 kredit <= 50/hari)",
        "scenes": 4,
        "duration_seconds": 4,
        "video_model": "omni-1.2-flash",
        "estimated_credits": 48,
        "sustainable_forever": True,
    },
    "hemat_3scene": {
        "label": "Super Hemat 3 Scene (3x5s = 45 kredit <= 50/hari)",
        "scenes": 3,
        "duration_seconds": 5,
        "video_model": "omni-1.2-flash",
        "estimated_credits": 45,
        "sustainable_forever": True,
    },
    "seimbang_60": {
        "label": "Seimbang (4x5s = 60 kredit, net -10/hari dari saldo)",
        "scenes": 4,
        "duration_seconds": 5,
        "video_model": "omni-1.2-flash",
        "estimated_credits": 60,
        "sustainable_forever": False,
    },
    "full_72": {
        "label": "Full 24 Detik (4x6s = 72 kredit, net -22/hari dari saldo)",
        "scenes": 4,
        "duration_seconds": 6,
        "video_model": "omni-1.2-flash",
        "estimated_credits": 72,
        "sustainable_forever": False,
    },
}


@dataclass
class DailyBudgetPolicy:
    daily_credit_limit: int = 50
    max_videos_per_day: int = 1
    daily_refill_credits: int = 50


@dataclass
class BudgetCheckResult:
    allowed: bool
    reason: str
    date_wib: str
    estimated_episode_credits: int
    per_clip_max_credits: int
    credits_spent_today: int
    videos_rendered_today: int
    remaining_daily_credits: int
    daily_credit_limit: int
    max_videos_per_day: int
    live_balance: int | None
    net_daily_delta: int
    estimated_runway_days: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def today_wib() -> str:
    return dt.datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d")


def estimate_clip_credits(video_model: str, duration_seconds: int) -> int:
    model = video_model.strip().lower()
    if model in CREDITS_PER_SECOND_BY_MODEL:
        return CREDITS_PER_SECOND_BY_MODEL[model] * duration_seconds
    if model in FLAT_CREDITS_PER_CLIP_BY_MODEL:
        return FLAT_CREDITS_PER_CLIP_BY_MODEL[model]
    return 3 * duration_seconds


def estimate_episode_credits(ep: EpisodeSpec) -> int:
    return sum(estimate_clip_credits(ep.video_model, s.duration_seconds) for s in ep.scenes)


def load_ledger(ledger_path: Path) -> dict[str, object]:
    if not ledger_path.exists():
        return {"policy": asdict(DailyBudgetPolicy()), "days": {}}
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"policy": asdict(DailyBudgetPolicy()), "days": {}}
        data.setdefault("policy", asdict(DailyBudgetPolicy()))
        data.setdefault("days", {})
        return data
    except Exception:
        return {"policy": asdict(DailyBudgetPolicy()), "days": {}}


def save_ledger(ledger_path: Path, data: dict[str, object]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_policy(ledger_path: Path) -> DailyBudgetPolicy:
    data = load_ledger(ledger_path)
    raw = data.get("policy", {})
    if not isinstance(raw, dict):
        return DailyBudgetPolicy()
    return DailyBudgetPolicy(
        daily_credit_limit=int(raw.get("daily_credit_limit", 50)),
        max_videos_per_day=int(raw.get("max_videos_per_day", 1)),
        daily_refill_credits=int(raw.get("daily_refill_credits", 50)),
    )


def update_policy(
    ledger_path: Path,
    daily_credit_limit: int,
    max_videos_per_day: int,
    daily_refill_credits: int = 50,
) -> DailyBudgetPolicy:
    data = load_ledger(ledger_path)
    policy = DailyBudgetPolicy(
        daily_credit_limit=max(1, int(daily_credit_limit)),
        max_videos_per_day=max(1, int(max_videos_per_day)),
        daily_refill_credits=max(0, int(daily_refill_credits)),
    )
    data["policy"] = asdict(policy)
    save_ledger(ledger_path, data)
    return policy


def get_day_stats(ledger_path: Path, date_str: str | None = None) -> dict[str, object]:
    key = date_str or today_wib()
    data = load_ledger(ledger_path)
    days = data.get("days", {})
    if not isinstance(days, dict):
        days = {}
    day = days.get(key, {"credits_spent": 0, "videos_rendered": 0, "runs": []})
    if not isinstance(day, dict):
        day = {"credits_spent": 0, "videos_rendered": 0, "runs": []}
    return {
        "date_wib": key,
        "credits_spent": int(day.get("credits_spent", 0)),
        "videos_rendered": int(day.get("videos_rendered", 0)),
        "runs": list(day.get("runs", [])),
    }


def record_render_spend(
    ledger_path: Path,
    episode_id: str,
    credits_spent: int,
    date_str: str | None = None,
) -> dict[str, object]:
    key = date_str or today_wib()
    data = load_ledger(ledger_path)
    days = data.setdefault("days", {})
    if not isinstance(days, dict):
        days = {}
        data["days"] = days
    entry = days.get(key, {"credits_spent": 0, "videos_rendered": 0, "runs": []})
    entry["credits_spent"] = int(entry.get("credits_spent", 0)) + max(0, int(credits_spent))
    entry["videos_rendered"] = int(entry.get("videos_rendered", 0)) + 1
    runs = list(entry.get("runs", []))
    runs.append(
        {
            "episode_id": episode_id,
            "credits_spent": max(0, int(credits_spent)),
            "timestamp_wib": dt.datetime.now(JAKARTA_TZ).isoformat(timespec="seconds"),
        }
    )
    entry["runs"] = runs
    days[key] = entry
    save_ledger(ledger_path, data)
    return entry


def check_render_budget(
    ep: EpisodeSpec,
    ledger_path: Path,
    live_balance: int | None = None,
    policy: DailyBudgetPolicy | None = None,
    override_limit: bool = False,
) -> BudgetCheckResult:
    pol = policy or get_policy(ledger_path)
    stats = get_day_stats(ledger_path)
    spent_today = int(stats["credits_spent"])
    videos_today = int(stats["videos_rendered"])
    est_credits = estimate_episode_credits(ep)
    per_clip_cap = max(estimate_clip_credits(ep.video_model, s.duration_seconds) for s in ep.scenes)
    remaining = max(0, pol.daily_credit_limit - spent_today)
    net_delta = pol.daily_refill_credits - est_credits

    runway: int | None = None
    if live_balance is not None:
        if net_delta >= 0:
            runway = 9999  # Sustainable indefinitely
        else:
            runway = max(0, live_balance // abs(net_delta))

    allowed = True
    reason = f"OK: estimasi {est_credits} kredit masuk batas harian ({remaining}/{pol.daily_credit_limit} tersisa)."

    if live_balance is not None and live_balance < est_credits:
        allowed = False
        reason = f"Saldo Google Flow tidak cukup ({live_balance} kredit < estimasi {est_credits} kredit)."
    elif not override_limit:
        if videos_today >= pol.max_videos_per_day:
            allowed = False
            reason = (
                f"Batas harian tercapai: sudah render {videos_today}/{pol.max_videos_per_day} video hari ini. "
                "Tunggu besok atau aktifkan Override jika memang ingin render lagi."
            )
        elif spent_today + est_credits > pol.daily_credit_limit:
            allowed = False
            reason = (
                f"Melebihi limit kredit harian: estimasi {est_credits} kredit + terpakai {spent_today} "
                f"> limit {pol.daily_credit_limit} kredit/hari. Gunakan preset hemat (4x4s = 48 kredit) "
                "atau aktifkan Override."
            )
    else:
        reason = f"Override aktif: estimasi {est_credits} kredit (limit normal {pol.daily_credit_limit}/hari)."

    return BudgetCheckResult(
        allowed=allowed,
        reason=reason,
        date_wib=str(stats["date_wib"]),
        estimated_episode_credits=est_credits,
        per_clip_max_credits=per_clip_cap,
        credits_spent_today=spent_today,
        videos_rendered_today=videos_today,
        remaining_daily_credits=remaining,
        daily_credit_limit=pol.daily_credit_limit,
        max_videos_per_day=pol.max_videos_per_day,
        live_balance=live_balance,
        net_daily_delta=net_delta,
        estimated_runway_days=runway,
    )
