"""Thu thập dữ liệu hằng ngày và ghi báo cáo JSON cho dashboard."""

from __future__ import annotations

import json
import datetime as dt
from pathlib import Path

from . import analyzer
from .sources import Fetcher, Suggestion, google_suggest, tiktok_suggest

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DATA_DIR = ROOT / "insights" / "data"
VN_TZ = dt.timezone(dt.timedelta(hours=7))


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_history(data_dir: Path, today: str, days: int) -> list[dict]:
    hist_dir = data_dir / "history"
    snaps = []
    for f in sorted(hist_dir.glob("*.json"))[-(days + 1):]:
        if f.stem >= today:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            snaps.append({"date": d["date"], "scores": {k["keyword"]: k["popularity"] for k in d["keywords"]}})
        except (OSError, KeyError, json.JSONDecodeError):
            print(f"  ! bỏ qua file lịch sử hỏng: {f.name}")
    return snaps


def collect(config: dict, fetcher: Fetcher | None = None, log=print) -> tuple[list[Suggestion], dict[str, list[str]], dict[str, str], Fetcher]:
    fetcher = fetcher or Fetcher(config.get("request_delay_seconds", 0.8), config.get("max_requests", 400))
    region, lang = config.get("region", "VN"), config.get("language", "vi")
    classifier = analyzer.Classifier(config)
    suggestions: list[Suggestion] = []
    seed_category: dict[str, str] = {}

    # Vòng 1: từ khóa gốc (+ biến thể) trên TikTok, Google và YouTube
    for cat in config["categories"]:
        log(f"[{cat['name']}]")
        for seed in cat["seeds"]:
            seed_category[seed] = cat["id"]
            for mod in config.get("modifiers", [""]):
                query = (seed + mod).strip()
                seed_category[query] = cat["id"]
                suggestions += tiktok_suggest(fetcher, query, region, lang)
            suggestions += google_suggest(fetcher, seed, lang)
            suggestions += google_suggest(fetcher, seed, lang, youtube=True)
        log(f"  {fetcher.count} request, {len(suggestions)} gợi ý")

    # Vòng 2: mở rộng các từ khóa hot nhất để lấy "tìm kiếm liên quan"
    prelim = analyzer.aggregate(suggestions, classifier, seed_category)
    top = sorted(prelim.values(), key=lambda i: -i["raw"])
    related: dict[str, list[str]] = {}
    n = 0
    for item in top:
        if n >= config.get("expand_top_n", 40) or fetcher.exhausted:
            break
        kw = item["keyword"]
        sugs = tiktok_suggest(fetcher, kw, region, lang)
        n += 1
        cat = next(iter(item["seed_categories"]), None)
        if cat:
            seed_category[kw] = cat
        suggestions += sugs
        related[kw] = [analyzer.normalize(s.keyword) for s in sugs if classifier.is_relevant(s.keyword)]
    log(f"Mở rộng {n} từ khóa. Tổng {fetcher.count} request, {fetcher.errors} lỗi.")
    return suggestions, related, seed_category, fetcher


def run(config: dict | None = None, data_dir: Path = DATA_DIR, today: str | None = None, log=print) -> dict:
    config = config or load_config()
    now = dt.datetime.now(VN_TZ)
    today = today or now.strftime("%Y-%m-%d")
    classifier = analyzer.Classifier(config)

    suggestions, related, seed_category, fetcher = collect(config, log=log)
    if not suggestions:
        raise SystemExit("Không lấy được dữ liệu nào (mạng bị chặn hoặc nguồn thay đổi). Không ghi đè báo cáo cũ.")

    history = load_history(data_dir, today, config.get("history_days", 30))
    agg = analyzer.aggregate(suggestions, classifier, seed_category)
    rows = select_rows(analyzer.build_report(agg, related, classifier, history, today), config)

    cats = [{"id": c["id"], "name": c["name"], "count": sum(c["id"] in r["categories"] for r in rows)} for c in config["categories"]]
    report = {
        "date": today,
        "generated_at": now.isoformat(timespec="seconds"),
        "region": config.get("region", "VN"),
        "stats": {
            "requests": fetcher.count,
            "errors": fetcher.errors,
            "raw_suggestions": len(suggestions),
            "keywords": len(rows),
            "history_days": len(history),
            "by_source": {src: sum(1 for s in suggestions if s.source == src) for src in ("tiktok", "google", "youtube")},
        },
        "categories": cats,
        "keywords": rows,
    }
    write_report(report, data_dir)
    log(f"Đã ghi {len(rows)} từ khóa vào {data_dir}")
    return report


def select_rows(rows: list[dict], config: dict) -> list[dict]:
    """Giữ top từ khóa toàn bộ + top mỗi nhóm để báo cáo gọn (vài trăm KB/ngày)."""
    keep = {r["keyword"] for r in rows[: config.get("max_keywords", 300)]}
    for cat in config["categories"]:
        in_cat = [r for r in rows if cat["id"] in r["categories"]]
        keep.update(r["keyword"] for r in in_cat[: config.get("min_per_category", 25)])
    return [r for r in rows if r["keyword"] in keep]


def write_report(report: dict, data_dir: Path) -> None:
    (data_dir / "history").mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    (data_dir / "latest.json").write_text(text, encoding="utf-8")
    (data_dir / "history" / f"{report['date']}.json").write_text(text, encoding="utf-8")
    dates = sorted((p.stem for p in (data_dir / "history").glob("*.json")), reverse=True)
    (data_dir / "index.json").write_text(json.dumps({"dates": dates}, ensure_ascii=False), encoding="utf-8")
