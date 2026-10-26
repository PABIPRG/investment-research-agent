import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from huohuo.server import Service


SCOPE = {"entity_id": "SEC:CN:A:600519", "exchange": "SSE", "operation": "quote_snapshot"}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Service({"host": "127.0.0.1", "port": 0, "principal": "owner", "user_token": "user-secret",
                                "worker_token": "worker-secret", "database": str(Path(self.temp.name) / "test.db")},
                               researcher=lambda scope: {"scope": scope, "status": "ok", "values": {"price": "12.1"}})
        self.thread = threading.Thread(target=self.service.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.service.server_port}"

    def tearDown(self):
        self.service.shutdown()
        self.service.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, body=None, token="user-secret", headers=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def test_security_search_auth_and_read_only(self):
        from unittest.mock import patch
        from huohuo.research_entities.security_search import reset_cache
        reset_cache()
        with patch("huohuo.research_entities.security_search.load_catalog", return_value=[{"code":"002518","name":"科士达"}]):
            self.assertEqual(403,self.call("/entities/search", {"query":"科士达"},token="worker-secret")[0])
            status,result=self.call("/entities/search", {"query":"科士达"})
            self.assertEqual(200,status)
            self.assertEqual("002518",result["candidates"][0]["code"])
            self.assertTrue(result["requires_confirmation"])
            self.assertEqual([],self.call("/mandates")[1]["items"])
            self.assertEqual([],self.call("/executions")[1]["executions"])
            self.assertEqual(400,self.call("/entities/search", {"query":"科士达","url":"https://evil.invalid"})[0])
        reset_cache()

    def create(self):
        status, job = self.call("/executions", {"request_key": "create", "scope": SCOPE, "question": "查看当前报价"})
        self.assertEqual(201, status)
        return job

    def claim(self):
        status, attempt = self.call("/worker/claim", {"worker_id": "test-worker"}, token="worker-secret")
        self.assertEqual(200, status)
        return attempt

    def test_identity_origin_and_role_boundaries(self):
        self.assertEqual(403, self.call("/health", token="bad")[0])
        self.assertEqual(403, self.call("/health", headers={"Origin": "https://attacker.invalid"})[0])
        self.assertEqual(403, self.call("/health", headers={"Host": "attacker.invalid"})[0])
        self.assertEqual(403, self.call("/worker/claim", {"worker_id": "fake"})[0])
        self.assertEqual(400, self.call("/executions", {"request_key": "k", "scope": SCOPE, "question": "q", "principal": "another"})[0])

    def test_recent_executions_are_bounded_and_principal_scoped(self):
        self.service.repo.create("another", "private", SCOPE, "不可见任务")
        self.assertEqual([], self.call("/executions")[1]["executions"])
        job = self.create()
        status, page = self.call("/executions")
        self.assertEqual(200, status)
        self.assertEqual([job], page["executions"])
        self.assertEqual(50, page["limit"])
        self.assertEqual(403, self.call("/executions", token="worker-secret")[0])

    def test_real_api_receipt_evidence_and_success(self):
        job, attempt = self.create(), self.claim()
        attempt_path = "/worker/attempts/" + attempt["attempt_id"]
        headers = {"X-Attempt-Token": attempt["lease_token"]}
        self.assertEqual(200, self.call(attempt_path + "/runtime", {"session_id": "s", "message_id": "m"}, "worker-secret", headers)[0])
        status, evidence = self.call("/attempts/" + attempt["attempt_id"] + "/research", {}, attempt["lease_token"])
        self.assertEqual(200, status)
        result = {"status": "succeeded", "execution_id": job["execution_id"], "scope": SCOPE,
                  "evidence_ids": [evidence["evidence_id"]], "summary": "已取得报价证据"}
        first = self.call(attempt_path + "/finish", result, "worker-secret", headers)
        self.assertEqual(200, first[0])
        self.assertEqual("succeeded", first[1]["status"])
        self.assertEqual(first, self.call(attempt_path + "/finish", result, "worker-secret", headers))
        events = self.call("/executions/" + job["execution_id"] + "/events")[1]
        self.assertIn("runtime.accepted", [event["kind"] for event in events])
        self.assertEqual(409, self.call("/attempts/" + attempt["attempt_id"] + "/research", {}, attempt["lease_token"])[0])

    def test_scope_cannot_be_replaced_and_capability_cannot_finish(self):
        self.create()
        attempt = self.claim()
        base = "/attempts/" + attempt["attempt_id"]
        self.assertEqual(400, self.call(base + "/research", {"scope": SCOPE}, attempt["lease_token"])[0])
        self.assertEqual(403, self.call("/worker" + base + "/finish", {"status": "failed", "error": "x"}, attempt["lease_token"])[0])

    def test_cancellation_during_collection_rejects_late_evidence(self):
        job, attempt = self.create(), self.claim()
        def collect(scope):
            self.service.repo.command("owner", job["execution_id"], "cancel", "cancel", attempt["revision"])
            return {"scope": scope, "status": "ok"}
        self.service.researcher = collect
        self.assertEqual(409, self.call("/attempts/" + attempt["attempt_id"] + "/research", {}, attempt["lease_token"])[0])
        self.assertEqual([], self.service.repo.evidence("owner", job["execution_id"]))


if __name__ == "__main__":
    unittest.main()
