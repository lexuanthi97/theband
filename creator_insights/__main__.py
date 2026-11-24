"""Creator Search Insights cho kênh tự động hóa.

    python -m creator_insights collect          # thu thập & tạo báo cáo hôm nay
    python -m creator_insights serve            # mở dashboard + tra cứu trực tiếp
    python -m creator_insights lookup "servo"   # tra nhanh trên terminal
"""

import argparse
import json
import sys

from .collect import load_config, run
from .server import lookup, serve


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # tiếng Việt trên Windows console
    p = argparse.ArgumentParser(prog="creator_insights", description="Tìm nội dung đang hot trên TikTok theo chủ đề của bạn")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect", help="Thu thập dữ liệu hôm nay và ghi vào insights/data")
    s = sub.add_parser("serve", help="Chạy dashboard tại máy (có tra cứu trực tiếp)")
    s.add_argument("--port", type=int, default=8765)
    lk = sub.add_parser("lookup", help="Tra cứu nhanh một từ khóa")
    lk.add_argument("query")
    args = p.parse_args(argv)

    if args.cmd == "collect":
        run()
    elif args.cmd == "serve":
        serve(args.port)
    elif args.cmd == "lookup":
        res = lookup(args.query, load_config())
        for r in res["keywords"][:25]:
            print(f"{r['popularity']:>3}  {r['keyword']:<45} {r['intent_label']:<10} {','.join(r['sources'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
