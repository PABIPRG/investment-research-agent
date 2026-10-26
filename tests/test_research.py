import unittest
from huohuo.research import snapshot
from huohuo.contracts import Invalid

SCOPE = {"entity_id": "SEC:CN:A:002518", "exchange": "SZSE", "operation": "quote_snapshot"}


class ResearchTests(unittest.TestCase):
    def test_non_stock_codes_are_rejected(self):
        for code, exchange in (("399001", "SZSE"), ("159915", "SZSE"), ("510300", "SSE"), ("110001", "SSE")):
            with self.assertRaises(Invalid):
                snapshot({"entity_id": "SEC:CN:A:" + code, "exchange": exchange, "operation": "quote_snapshot"})

    def test_malformed_and_rejected_responses_are_not_empty(self):
        scope = {"entity_id": "SEC:CN:A:600519", "exchange": "SSE", "operation": "quote_snapshot"}
        for raw in ({}, {"rc": 1, "data": None}, {"data": {}}, {"data": {"diff": [None]}}):
            self.assertEqual("error", snapshot(scope, lambda _: (raw, "https://example.invalid/fixture"))["status"])
        self.assertEqual("empty", snapshot(scope, lambda _: ({"rc": 0, "data": {"diff": []}}, "https://example.invalid/fixture"))["status"])

    def test_deterministic_calculation_and_source(self):
        def loader(_):
            return {"data": {"diff": [{"f12": "002518", "f14": "测试证券", "f2": 12.1, "f18": 10, "f124": 1700000000}]}}, "https://example.invalid/fixture"
        result = snapshot(SCOPE, loader)
        self.assertEqual("ok", result["status"])
        self.assertEqual("2.1", result["values"]["change"])
        self.assertEqual("21.0000", result["values"]["change_percent"])
        self.assertTrue(result["data_as_of"])
        self.assertEqual(SCOPE, result["scope"])

    def test_missing_is_not_zero(self):
        result = snapshot(SCOPE, lambda _: ({"data": {"diff": [{"f12": "002518", "f2": "-", "f18": 10}]}}, "fixture"))
        self.assertEqual("unavailable", result["status"])
        self.assertNotIn("values", result)

    def test_failure_is_not_empty(self):
        def fail(_):
            raise TimeoutError("sensitive details must not be returned")
        result = snapshot(SCOPE, fail)
        self.assertEqual("error", result["status"])
        self.assertNotIn("sensitive", str(result))
        self.assertEqual("empty", snapshot(SCOPE, lambda _: ({"data": {"diff": []}}, "fixture"))["status"])

    def test_scope_identity_not_reparsed(self):
        with self.assertRaises(Invalid):
            snapshot({**SCOPE, "exchange": "SSE"})

