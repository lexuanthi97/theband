import unittest

from creator_insights import analyzer
from creator_insights.collect import load_config
from creator_insights.sources import Suggestion


class AnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.clf = analyzer.Classifier(cls.config)

    def test_relevance(self):
        for kw in ["lập trình plc", "servo delta", "cài đặt biến tần ls", "hmi weintek", "lap trinh plc", "mitsubishi lập trình"]:
            self.assertTrue(self.clf.is_relevant(kw), kw)
        for kw in ["lập trình game", "laptop cho lập trình viên", "delta force", "giá vàng hôm nay", "gia công cnc"]:
            self.assertFalse(self.clf.is_relevant(kw), kw)

    def test_categories(self):
        self.assertEqual(self.clf.categories_for("plc s7 1200"), ["plc"])
        self.assertIn("sales", self.clf.categories_for("giá servo mitsubishi"))
        self.assertIn("servo", self.clf.categories_for("giá servo mitsubishi"))
        self.assertNotIn("sales", self.clf.categories_for("bàn phím plc"))

    def test_intent(self):
        self.assertEqual(self.clf.intent("plc là gì"), "question")
        self.assertEqual(self.clf.intent("lập trình plc dùng ngôn ngữ gì"), "question")
        self.assertEqual(self.clf.intent("giá plc mitsubishi"), "commercial")
        self.assertEqual(self.clf.intent("học plc cơ bản"), "learn")
        self.assertEqual(self.clf.intent("cách đấu dây servo"), "howto")
        self.assertEqual(self.clf.intent("plc fx3u"), "product")
        self.assertEqual(self.clf.intent("gia công cnc"), "topic")

    def test_scoring_and_trend(self):
        sugs = [
            Suggestion("plc mitsubishi", "tiktok", "plc", 0, 10, ctr=0.01),
            Suggestion("plc mitsubishi", "tiktok", "plc mitsubishi", 0, 10),
            Suggestion("plc mitsubishi", "google", "plc", 1, 10),
            Suggestion("plc omron", "tiktok", "plc", 8, 10),
            Suggestion("lập trình game", "tiktok", "lập trình", 0, 10),
            Suggestion("hmi weintek giá", "google", "hmi", 0, 10),
            Suggestion("hmi weintek giá", "youtube", "hmi", 0, 10),
            Suggestion("cảm biến ô tô", "tiktok", "cảm biến", 0, 10),
        ]
        agg = analyzer.aggregate(sugs, self.clf, {"plc": "plc"})
        self.assertNotIn("lập trình game", agg)
        self.assertNotIn("cảm biến ô tô", agg)  # exclude_terms
        history = [
            {"date": "2026-11-22", "scores": {"plc mitsubishi": 60, "plc omron": 90}},
            {"date": "2026-11-23", "scores": {"plc mitsubishi": 70, "plc omron": 90}},
        ]
        rows = {r["keyword"]: r for r in analyzer.build_report(agg, {}, self.clf, history, "2026-11-24")}
        self.assertEqual(rows["plc mitsubishi"]["popularity"], 100)
        self.assertLess(rows["plc omron"]["popularity"], 100)
        self.assertEqual(rows["plc mitsubishi"]["trend"]["status"], "rising")
        self.assertEqual(rows["plc omron"]["trend"]["status"], "falling")
        self.assertEqual(rows["hmi weintek giá"]["trend"]["status"], "new")
        self.assertTrue(rows["hmi weintek giá"]["opportunity"])  # có trên Google + YouTube, chưa có trên TikTok
        self.assertEqual(rows["plc mitsubishi"]["trend"]["series"][-1], {"date": "2026-11-24", "value": 100})
        self.assertTrue(rows["plc mitsubishi"]["tiktok_url"].startswith("https://www.tiktok.com/search?q=plc%20mitsubishi"))

    def test_hashtag(self):
        self.assertEqual(analyzer.to_hashtag("Lập trình PLC đơn giản"), "#laptrinhplcdongian")


if __name__ == "__main__":
    unittest.main()
