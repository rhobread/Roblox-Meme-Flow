from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from typing import Literal

import httpx

GOOGLE_TRENDS_ID_RSS = "https://trends.google.com/trending/rss?geo=ID"
JAKARTA_TZ = dt.timezone(dt.timedelta(hours=7), "WIB")

ALGORITHM_PLAYBOOK: dict[str, list[str]] = {
    "youtube_shorts": [
        "Stop swipe-away di 0-2 detik pertama dengan kontras visual ekstrem + kalimat pembuka 'Di dunia ini...'.",
        "Targetkan Average Percentage Viewed >95% dengan durasi padat 16-24 detik tanpa jeda mati.",
        "Buat transisi ending nyambung halus ke awal (loopable) untuk mendorong replay otomatis.",
    ],
    "tiktok_fyp": [
        "Visual hook harus langsung jelas meski suara dimatikan (50% viewer scroll mute di 1 detik pertama).",
        "Gunakan micro-pacing: ganti aksi/angle tiap scene (4-6 detik) dengan ekspresi deadpan atau slapstick.",
        "Tutup dengan pancingan komentar atau tag teman yang relatable di Indonesia.",
    ],
    "instagram_reels": [
        "Optimalkan DM Shares (Sends per reach) dengan topik sehari-hari yang bikin orang kirim ke teman/grup WA.",
        "Gunakan subtitle kontras tinggi di tengah-bawah aman dari UI Reels (MarginV=85) dan BGM ikonik.",
        "Eksport bersih tanpa watermark platform lain agar tidak terkena demosi algoritma.",
    ],
}

EVERGREEN_VIRAL_ANGLES: dict[str, list[str]] = {
    "meme_roblox_id": [
        "Utang kecil ke teman/warung yang berubah jadi efek visual absurd (strobo, label melayang, magnet)",
        "Avatar polos/noob diremehkan avatar sultan lalu membalikkan keadaan (karma twist klasik)",
        "Kebiasaan chat grup WA Indonesia: cuma read, bilang OTW masih rebahan, janji wacana nongkrong",
        "Tragedi akhir bulan / saldo e-wallet menentukan ukuran badan atau gravitasi karakter",
        "Drama sekolah/kuliah/kantor Indonesia (dosen revisi jadi boss fight, AC kosan jadi kutub utara)",
    ],
    "kids_animation_id": [
        "Hewan lucu atau mainan blok belajar berbagi/jujur dengan keajaiban warna-warni (balon, pelangi, permen)",
        "Petualangan mini di dunia permen / dunia awan dengan teka-teki interaktif ('Coba hitung ada berapa bintang?')",
        "Karakter ceria membantu teman kecil yang kesulitan lalu dapat kejutan magis penuh tawa",
        "Kebiasaan baik harian anak (sikat gigi, bereskan mainan, makan sayur) diubah jadi misi superhero lucu",
    ],
}


@dataclass
class TrendItem:
    title: str
    traffic: str = ""
    source: str = "google_trends_id"


@dataclass
class ViralResearchBrief:
    generated_at_wib: str
    content_mode: Literal["meme_roblox_id", "kids_animation_id"]
    topic_hint: str
    live_trends_id: list[TrendItem] = field(default_factory=list)
    fetch_warning: str | None = None
    algorithm_rules: dict[str, list[str]] = field(default_factory=lambda: dict(ALGORITHM_PLAYBOOK))
    recommended_angles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_prompt_block(self) -> str:
        lines = [
            f"## Live Viral Research Brief ({self.generated_at_wib})",
            f"- Content Mode: `{self.content_mode}`",
        ]
        if self.topic_hint:
            lines.append(f"- User Topic Hint: {self.topic_hint}")
        if self.live_trends_id:
            lines.append("- Live Trending Topics in Indonesia (Google Trends RSS):")
            for item in self.live_trends_id[:10]:
                suffix = f" ({item.traffic})" if item.traffic else ""
                lines.append(f"  - {item.title}{suffix}")
        elif self.fetch_warning:
            lines.append(f"- Live Trends Note: {self.fetch_warning} (using evergreen Indonesian viral angles)")

        lines.append("- High-Retention Viral Angles:")
        for angle in self.recommended_angles:
            lines.append(f"  - {angle}")

        lines.append("- Multi-Platform Algorithm Requirements (YouTube Shorts + TikTok + Instagram Reels):")
        for platform, rules in self.algorithm_rules.items():
            lines.append(f"  - {platform}: " + " ".join(rules))
        return "\n".join(lines)


def fetch_google_trends_id(limit: int = 12, timeout_s: float = 8.0) -> tuple[list[TrendItem], str | None]:
    """Fetch live daily trending queries from Google Trends Indonesia RSS (zero cost, no API key)."""
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.get(
                GOOGLE_TRENDS_ID_RSS,
                headers={"User-Agent": "Mozilla/5.0 (compatible; RobloxMemeFlow/1.0)"},
            )
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items: list[TrendItem] = []
        ns_ht = "{https://trends.google.com/trending/rss}"
        for item in root.findall(".//item"):
            title_el = item.find("title")
            if title_el is None or not title_el.text:
                continue
            traffic_el = item.find(f"{ns_ht}approx_traffic")
            traffic = traffic_el.text.strip() if traffic_el is not None and traffic_el.text else ""
            items.append(TrendItem(title=title_el.text.strip(), traffic=traffic))
            if len(items) >= limit:
                break
        return items, None
    except Exception as exc:
        return [], f"Could not fetch live Google Trends RSS: {exc}"


def build_viral_research_brief(
    content_mode: Literal["meme_roblox_id", "kids_animation_id"] = "meme_roblox_id",
    topic_hint: str = "",
    fetch_live: bool = True,
) -> ViralResearchBrief:
    now_wib = dt.datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M WIB")
    trends: list[TrendItem] = []
    warning: str | None = None
    if fetch_live:
        trends, warning = fetch_google_trends_id()
    return ViralResearchBrief(
        generated_at_wib=now_wib,
        content_mode=content_mode,
        topic_hint=topic_hint.strip(),
        live_trends_id=trends,
        fetch_warning=warning,
        recommended_angles=list(EVERGREEN_VIRAL_ANGLES[content_mode]),
    )
