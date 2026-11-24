"""Nguồn dữ liệu: gợi ý tìm kiếm TikTok, Google và YouTube.

Chỉ dùng thư viện chuẩn của Python để chạy được ở mọi nơi
(GitHub Actions, Windows, Linux) mà không cần cài thêm gói.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class Suggestion:
    """Một gợi ý tìm kiếm do một nguồn trả về cho một từ khóa gốc."""

    keyword: str
    source: str  # "tiktok" | "google" | "youtube"
    seed: str
    position: int  # 0 = vị trí đầu tiên (được tìm nhiều nhất)
    total: int  # số gợi ý trong cùng lần trả về
    ctr: float = 0.0  # predict_ctr_score của TikTok (nếu có)
    hot_level: int = 0  # hot_level của TikTok (0 = bình thường)
    time_sensitive: bool = False  # TikTok đánh dấu là từ khóa theo thời điểm
    extra: dict = field(default_factory=dict)


class Fetcher:
    """HTTP client đơn giản có giới hạn tốc độ và số lượng request."""

    def __init__(self, delay: float = 0.8, max_requests: int = 400, timeout: float = 15):
        self.delay = delay
        self.max_requests = max_requests
        self.timeout = timeout
        self.count = 0
        self.errors = 0
        self._last = 0.0

    @property
    def exhausted(self) -> bool:
        return self.count >= self.max_requests

    def get_json(self, url: str):
        if self.exhausted:
            return None
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.count += 1
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    charset = resp.headers.get_content_charset() or "utf-8"
                return json.loads(raw.decode(charset, errors="replace"))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError) as exc:
                if attempt == 2:
                    self.errors += 1
                    print(f"  ! lỗi khi gọi {url[:90]}…: {exc}")
                    return None
                time.sleep(1.5 * (attempt + 1))
        return None


def tiktok_suggest(fetcher: Fetcher, seed: str, region: str = "VN", lang: str = "vi") -> list[Suggestion]:
    """Gợi ý tìm kiếm của TikTok (giống ô tìm kiếm trong app)."""
    params = urllib.parse.urlencode(
        {"keyword": seed, "aid": "1988", "app_language": lang, "region": region, "priority_region": region}
    )
    data = fetcher.get_json(f"https://www.tiktok.com/api/search/general/sug/?{params}")
    if not data:
        return []
    items = data.get("sug_list") or []
    out = []
    for i, item in enumerate(items):
        text = (item.get("content") or "").strip()
        if not text:
            continue
        extra = item.get("extra_info") or {}
        out.append(
            Suggestion(
                keyword=text,
                source="tiktok",
                seed=seed,
                position=i,
                total=len(items),
                ctr=_to_float(extra.get("predict_ctr_score")),
                hot_level=int(_to_float(extra.get("hot_level"))),
                time_sensitive=str(extra.get("is_time_sensitive", "0")) == "1",
            )
        )
    return out


def google_suggest(fetcher: Fetcher, seed: str, lang: str = "vi", youtube: bool = False) -> list[Suggestion]:
    """Gợi ý tìm kiếm của Google (web) hoặc YouTube (ds=yt)."""
    params = {"client": "firefox", "hl": lang, "q": seed}
    if youtube:
        params["ds"] = "yt"
    data = fetcher.get_json("https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(params))
    if not data or len(data) < 2:
        return []
    items = [s for s in data[1] if isinstance(s, str)]
    source = "youtube" if youtube else "google"
    return [
        Suggestion(keyword=s.strip(), source=source, seed=seed, position=i, total=len(items))
        for i, s in enumerate(items)
        if s.strip()
    ]


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
