"""Phân tích: lọc từ khóa đúng chủ đề, phân nhóm, chấm điểm độ hot,
so sánh xu hướng theo ngày, tìm cơ hội nội dung và gợi ý ý tưởng video."""

from __future__ import annotations

import math
import re
import unicodedata
import urllib.parse
from collections import defaultdict

from .sources import Suggestion

SOURCE_WEIGHT = {"tiktok": 1.0, "google": 0.6, "youtube": 0.6}

INTENT_PATTERNS = [
    ("question", ["là gì", "làm gì", "tại sao", "vì sao", "có khó không", "có nên", "như thế nào", "bao nhiêu", "khác nhau", "ngôn ngữ gì", "loại nào", "what is", "why"]),
    ("commercial", ["giá", "mua", "bán", "báo giá", "cũ", "giá rẻ", "chính hãng", "thanh lý", "review", "so sánh", "tốt nhất", "price"]),
    ("learn", ["học", "cơ bản", "cho người mới", "khóa học", "tài liệu", "bài tập", "giáo trình", "course", "basic", "beginner"]),
    ("howto", ["cách", "hướng dẫn", "cài đặt", "đấu dây", "đấu nối", "cấu hình", "sửa", "khắc phục", "lỗi", "how to", "tutorial", "setup", "wiring"]),
]

INTENT_LABELS = {
    "question": "Hỏi đáp",
    "howto": "Hướng dẫn",
    "learn": "Học tập",
    "commercial": "Mua bán",
    "product": "Sản phẩm",
    "topic": "Chủ đề",
}

IDEA_TEMPLATES = {
    "question": [
        "Trả lời nhanh trong 60 giây: “{k}”",
        "3 hiểu lầm phổ biến về {k} (kèm ví dụ thực tế)",
        "Kỹ sư trả lời: {k} — quay tại tủ điện thật",
    ],
    "howto": [
        "Hướng dẫn {k} từng bước (quay màn hình + thiết bị thật)",
        "Lỗi hay gặp khi {k} và cách xử lý",
        "Làm thử {k} trong 1 phút — lưu lại để làm theo",
    ],
    "learn": [
        "Series {k} cho người mới — Tập 1",
        "Lộ trình tự học {k} trong 30 ngày",
        "Bài tập nhỏ về {k} — bình luận đáp án",
    ],
    "commercial": [
        "Báo giá & so sánh: {k} — nên chọn loại nào?",
        "Test hàng trước khi giao khách: {k}",
        "Mẹo kiểm tra {k} cũ trước khi mua",
    ],
    "product": [
        "Đấu dây & cài đặt {k} thực tế",
        "Unbox {k} — thông số cần biết trước khi dùng",
        "Ứng dụng {k} trong máy thực tế tại xưởng",
    ],
    "topic": [
        "Ứng dụng thực tế của {k} trong nhà máy",
        "{k}: điều mình ước biết sớm hơn khi mới vào nghề",
        "Trước & sau khi áp dụng {k} cho một dây chuyền",
    ],
}


# ---------------------------------------------------------------- text utils

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower().strip()
    return re.sub(r"\s+", " ", text)


def fold(text: str) -> str:
    """Bỏ dấu tiếng Việt: 'lập trình' -> 'lap trinh'."""
    text = normalize(text).replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def contains_term(text: str, term: str) -> bool:
    """So khớp nguyên từ. Chỉ so khớp kiểu bỏ dấu khi người dùng gõ không dấu
    (tránh nhầm "gia công" với "giá", "bàn" với "bán")."""
    text_n = normalize(text)
    pairs = [(normalize(term), text_n)]
    if fold(text_n) == text_n:
        pairs.append((fold(term), text_n))
    for t, s in pairs:
        if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", s):
            return True
    return False


def to_hashtag(text: str) -> str:
    return "#" + re.sub(r"[^a-z0-9]", "", fold(text))


def tiktok_search_url(keyword: str) -> str:
    return "https://www.tiktok.com/search?q=" + urllib.parse.quote(keyword)


# ---------------------------------------------------------------- classify

class Classifier:
    def __init__(self, config: dict):
        self.categories = config["categories"]
        self.brands = config.get("brands", [])
        self.weak = config.get("weak_terms", [])
        self.exclude = config.get("exclude_terms", [])
        self.sales_terms = next((c["terms"] for c in self.categories if c["id"] == "sales"), [])

    def categories_for(self, keyword: str) -> list[str]:
        cats = []
        for cat in self.categories:
            if cat["id"] == "sales":
                continue
            if any(contains_term(keyword, t) for t in cat["terms"]):
                cats.append(cat["id"])
        if any(contains_term(keyword, t) for t in self.sales_terms) and (cats or self.has_brand(keyword)):
            cats.append("sales")
        return cats

    def has_brand(self, keyword: str) -> bool:
        return any(contains_term(keyword, b) for b in self.brands)

    def is_relevant(self, keyword: str) -> bool:
        if any(contains_term(keyword, t) for t in self.exclude):
            return False
        if self.categories_for(keyword):
            return True
        # Hãng + từ ngữ cảnh kỹ thuật (vd: "mitsubishi lập trình")
        if self.has_brand(keyword) and any(contains_term(keyword, w) for w in self.weak):
            return True
        return False

    def intent(self, keyword: str) -> str:
        if keyword.strip().endswith("?"):
            return "question"
        for name, patterns in INTENT_PATTERNS:
            if any(contains_term(keyword, p) for p in patterns):
                return name
        if self.has_brand(keyword) or re.search(r"\d", keyword):
            return "product"
        return "topic"


# ---------------------------------------------------------------- scoring

def position_weight(position: int) -> float:
    return (10 - min(position, 9)) / 10


def aggregate(
    suggestions: list[Suggestion],
    classifier: Classifier,
    seed_category: dict[str, str],
    filter_relevant: bool = True,
) -> dict[str, dict]:
    """Gom các gợi ý trùng nhau, giữ lại từ khóa đúng chủ đề."""
    agg: dict[str, dict] = {}
    for s in suggestions:
        key = normalize(s.keyword)
        if not key or len(key) > 80:
            continue
        if filter_relevant and not classifier.is_relevant(key):
            continue
        item = agg.setdefault(
            key,
            {
                "keyword": key,
                "raw": 0.0,
                "sources": defaultdict(int),
                "seeds": set(),
                "hot": 0,
                "time_sensitive": False,
                "ctr": 0.0,
                "seed_categories": set(),
            },
        )
        echo = 0.3 if key == normalize(s.seed) else 1.0
        item["raw"] += SOURCE_WEIGHT.get(s.source, 0.5) * position_weight(s.position) * echo
        item["sources"][s.source] += 1
        item["seeds"].add(s.seed)
        item["hot"] = max(item["hot"], s.hot_level)
        item["time_sensitive"] |= s.time_sensitive
        item["ctr"] = max(item["ctr"], s.ctr)
        if s.seed in seed_category:
            item["seed_categories"].add(seed_category[s.seed])
    for item in agg.values():
        item["raw"] += 2.0 * item["hot"] + 1.5 * item["time_sensitive"] + 50 * item["ctr"]
    return agg


def popularity_scores(agg: dict[str, dict]) -> None:
    if not agg:
        return
    top = max(i["raw"] for i in agg.values())
    for item in agg.values():
        item["popularity"] = max(1, round(100 * math.log1p(item["raw"]) / math.log1p(top)))


def trend_for(keyword: str, today_value: int, history: list[dict], today: str, window: int = 7, series_days: int = 14):
    """history: danh sách snapshot cũ [{date, scores: {kw: popularity}}], sắp theo ngày tăng dần."""
    past = [h for h in history if h["date"] < today]
    recent = past[-window:]
    series = [{"date": h["date"], "value": h["scores"].get(keyword, 0)} for h in past[-(series_days - 1):]]
    series.append({"date": today, "value": today_value})
    if not recent:
        return {"status": "baseline", "delta": 0, "series": series}
    seen_before = any(keyword in h["scores"] for h in past)
    avg = sum(h["scores"].get(keyword, 0) for h in recent) / len(recent)
    delta = round(today_value - avg)
    if not seen_before:
        status = "new"
    elif delta >= 12:
        status = "rising"
    elif delta <= -12:
        status = "falling"
    else:
        status = "stable"
    return {"status": status, "delta": delta, "series": series}


def opportunity(item: dict, intent: str, related_count: int | None) -> tuple[bool, str]:
    """Ước tính 'khoảng trống nội dung': người ta tìm nhưng TikTok còn ít gợi ý liên quan."""
    tiktok_hits = item["sources"].get("tiktok", 0)
    offsite_sources = sum(1 for s in ("google", "youtube") if item["sources"].get(s))
    pop = item["popularity"]
    if offsite_sources == 2 and tiktok_hits == 0 and pop >= 15:
        return True, "Được tìm trên cả Google và YouTube nhưng chưa có trong gợi ý TikTok — ít người làm"
    if related_count is not None and related_count <= 2 and pop >= 40:
        return True, "Được tìm nhiều nhưng TikTok gần như không có tìm kiếm liên quan — ít đối thủ"
    if intent in ("question", "howto", "learn") and offsite_sources and tiktok_hits <= 1 and pop >= 30:
        return True, "Câu hỏi/hướng dẫn được tìm trên nhiều nền tảng — nên có video giải đáp"
    return False, ""


def ideas_for(keyword: str, intent: str) -> list[str]:
    return [t.format(k=keyword) for t in IDEA_TEMPLATES.get(intent, IDEA_TEMPLATES["topic"])]


def build_report(
    agg: dict[str, dict],
    related: dict[str, list[str]],
    classifier: Classifier,
    history: list[dict],
    today: str,
) -> list[dict]:
    popularity_scores(agg)
    cat_tags = {c["id"]: c.get("hashtags", []) for c in classifier.categories}
    rows = []
    for key, item in agg.items():
        cats = classifier.categories_for(key) or sorted(item["seed_categories"])[:1]
        intent = classifier.intent(key)
        rel = [r for r in related.get(key, []) if r != key]
        is_opp, why = opportunity(item, intent, len(rel) if key in related else None)
        tags = [to_hashtag(key)]
        for c in cats:
            tags += cat_tags.get(c, [])
        tags = list(dict.fromkeys(t for t in tags if len(t) > 2))[:6]
        rows.append(
            {
                "keyword": key,
                "categories": cats,
                "intent": intent,
                "intent_label": INTENT_LABELS[intent],
                "popularity": item["popularity"],
                "sources": dict(item["sources"]),
                "seed_count": len(item["seeds"]),
                "hot": item["hot"],
                "time_sensitive": item["time_sensitive"],
                "trend": trend_for(key, item["popularity"], history, today),
                "opportunity": is_opp,
                "opportunity_reason": why,
                "related": rel[:10],
                "ideas": ideas_for(key, intent),
                "hashtags": tags,
                "tiktok_url": tiktok_search_url(key),
            }
        )
    rows.sort(key=lambda r: (-r["popularity"], r["keyword"]))
    return rows
