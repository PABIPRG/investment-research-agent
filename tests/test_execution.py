import concurrent.futures
import tempfile
import threading
import unittest
import sqlite3
import subprocess
import sys
from unittest.mock import patch
from pathlib import Path

from huohuo.execution import Conflict, Missing, Repository


SCOPE = {"entity_id": "SEC:CN:A:002518", "exchange": "SZSE", "operation": "quote_snapshot"}


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "business.sqlite3"
        self.now = 1000.0
        self.repo = Repository(self.path, clock=lambda: self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, key="request-1"):
        return self.repo.create("owner", key, SCOPE, "请解释本次快照及数据限制")

    def test_create_idempotency_and_changed_payload(self):
        first = self.create()
        self.assertEqual(first, self.create())
        with self.assertRaises(Conflict):
            self.repo.create("owner", "request-1", SCOPE, "不同问题")
        self.assertNotEqual(first["execution_id"], self.repo.create("another", "request-1", SCOPE, "另一个主体")["execution_id"])

    def test_two_connections_claim_once(self):
        self.create()
        barrier = threading.Barrier(2)
        def claim(worker):
            repo = Repository(self.path, clock=lambda: self.now)
            barrier.wait()
            return repo.claim(worker, 30)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(claim, ["a", "b"]))
        self.assertEqual(1, sum(r is not None for r in results))

    def test_cancel_receipt_replay_and_stale_version(self):
        item = self.create()
        receipt = self.repo.command("owner", item["execution_id"], "cancel", "cancel-1", 1)
        self.assertEqual(receipt, self.repo.command("owner", item["execution_id"], "cancel", "cancel-1", 1))
        with self.assertRaises(Conflict):
            self.repo.command("owner", item["execution_id"], "cancel", "cancel-2", 1)
        self.assertIsNone(self.repo.claim("worker", 30))

    def test_cancel_running_rejects_result(self):
        item = self.create()
        attempt = self.repo.claim("worker", 30)
        self.repo.command("owner", item["execution_id"], "cancel", "cancel", 2)
        with self.assertRaises(Conflict):
            self.repo.finish(attempt["attempt_id"], attempt["lease_token"], {"status": "failed", "error": "late"})
        self.assertEqual("cancelled", self.repo.get("owner", item["execution_id"])["status"])

    def test_expiry_requires_explicit_retry_and_fences_old_attempt(self):
        item = self.create()
        a = self.repo.claim("worker-a", 30)
        self.now += 30
        with self.assertRaises(Conflict):
            self.repo.heartbeat(a["attempt_id"], a["lease_token"], 30)
        self.assertEqual(1, self.repo.recover())
        self.assertIsNone(self.repo.claim("worker-b", 30))
        current = self.repo.get("owner", item["execution_id"])
        self.assertEqual("interrupted", current["status"])
        self.repo.command("owner", item["execution_id"], "retry", "retry", current["revision"])
        b = self.repo.claim("worker-b", 30)
        self.assertGreater(b["fence"], a["fence"])
        with self.assertRaises(Conflict):
            self.repo.finish(a["attempt_id"], a["lease_token"], {"status": "failed", "error": "late"})

    def test_result_commit_replay_and_payload_conflict(self):
        item = self.create()
        attempt = self.repo.claim("worker", 30)
        result = {"status": "failed", "error": "source unavailable"}
        first = self.repo.finish(attempt["attempt_id"], attempt["lease_token"], result)
        self.assertEqual(first, self.repo.finish(attempt["attempt_id"], attempt["lease_token"], result))
        with self.assertRaises(Conflict):
            self.repo.finish(attempt["attempt_id"], attempt["lease_token"], {"status": "failed", "error": "different"})
        self.assertEqual("failed", self.repo.get("owner", item["execution_id"])["status"])

    def test_restart_preserves_queued_and_recovers_expired_only(self):
        running = self.create("one")
        self.repo.claim("worker", 30)
        queued = self.create("two")
        reopened = Repository(self.path, clock=lambda: self.now)
        self.assertEqual(0, reopened.recover())
        self.now += 31
        self.assertEqual(1, reopened.recover())
        self.assertEqual("interrupted", reopened.get("owner", running["execution_id"])["status"])
        self.assertEqual("queued", reopened.get("owner", queued["execution_id"])["status"])

    def test_heartbeat_does_not_change_user_revision(self):
        item = self.create()
        attempt = self.repo.claim("worker", 30)
        self.now += 5
        self.repo.heartbeat(attempt["attempt_id"], attempt["lease_token"], 30)
        self.assertEqual(2, self.repo.get("owner", item["execution_id"])["revision"])

    def test_success_requires_evidence_from_same_attempt(self):
        item = self.create()
        attempt = self.repo.claim("worker", 30)
        with self.assertRaises(Conflict):
            self.repo.finish(attempt["attempt_id"], attempt["lease_token"], {"status": "succeeded", "execution_id": item["execution_id"], "scope": SCOPE, "evidence_ids": ["invented"], "summary": "没有证据"})

    def test_unknown_schema_is_not_modified(self):
        path = Path(self.tmp.name) / "future.db"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE schema_info(version INTEGER)")
            db.execute("INSERT INTO schema_info VALUES(2)")
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "unsupported"):
            Repository(path)
        self.assertEqual(before, path.read_bytes())

    def test_schema_initialization_failure_is_atomic(self):
        path = Path(self.tmp.name) / "partial.db"
        connect = sqlite3.connect
        def interrupted(*args, **kwargs):
            db = connect(*args, **kwargs)
            db.set_authorizer(lambda action, name, *_: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE and name == "events" else sqlite3.SQLITE_OK)
            return db
        with patch("huohuo.execution.sqlite3.connect", interrupted):
            with self.assertRaises(sqlite3.DatabaseError):
                Repository(path)
        with connect(path) as db:
            self.assertEqual([], db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
        Repository(path)

    def test_claim_failure_rolls_back_state_attempt_and_event(self):
        item = self.create()
        with patch.object(self.repo, "_event", side_effect=RuntimeError("injected transaction failure")):
            with self.assertRaises(RuntimeError):
                self.repo.claim("worker")
        self.assertEqual("queued", self.repo.get("owner", item["execution_id"])["status"])
        with self.repo.connection() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM attempts").fetchone()[0])
        self.assertEqual(1, len(self.repo.history("owner", item["execution_id"])))

    def test_cancel_revokes_all_attempt_capabilities(self):
        item = self.create()
        a = self.repo.claim("w")
        self.repo.command("owner", item["execution_id"], "cancel", "cancel", 2)
        for call in (
            lambda: self.repo.heartbeat(a["attempt_id"], a["lease_token"]),
            lambda: self.repo.runtime_receipt(a["attempt_id"], a["lease_token"], {"session_id": "s", "message_id": "m"}),
            lambda: self.repo.save_evidence(a["attempt_id"], a["lease_token"], {"scope": SCOPE, "status": "ok"}),
            lambda: self.repo.finish(a["attempt_id"], a["lease_token"], {"status": "failed", "error": "late"}),
        ):
            with self.assertRaises(Conflict): call()

    def test_retry_competition_and_old_receipt_cannot_overwrite_new_attempt(self):
        item = self.create()
        a = self.repo.claim("w")
        failed = {"status": "failed", "error": "known failure"}
        receipt = self.repo.finish(a["attempt_id"], a["lease_token"], failed)
        self.repo.command("owner", item["execution_id"], "retry", "retry1", receipt["revision"])
        with self.assertRaises(Conflict):
            self.repo.command("owner", item["execution_id"], "retry", "retry2", receipt["revision"])
        b = self.repo.claim("w")
        self.assertEqual(receipt, self.repo.finish(a["attempt_id"], a["lease_token"], failed))
        self.assertEqual(b["attempt_id"], self.repo.get("owner", item["execution_id"])["current_attempt"])
        self.assertEqual("running", self.repo.get("owner", item["execution_id"])["status"])

    def test_separate_process_exit_leaves_durable_claim(self):
        item = self.create()
        subprocess.run([sys.executable, "-c", "import sys; from huohuo.execution import Repository; Repository(sys.argv[1], clock=lambda: 1000).claim('child', 5)", str(self.path)], check=True)
        self.assertEqual("running", self.repo.get("owner", item["execution_id"])["status"])
        self.now += 6
        self.assertEqual(1, self.repo.recover())
        self.assertIsNone(self.repo.claim("next"))

    def test_principal_cannot_read_or_cancel_another_execution(self):
        item = self.create()
        with self.assertRaises(Missing): self.repo.get("other", item["execution_id"])
        with self.assertRaises(Missing): self.repo.command("other", item["execution_id"], "cancel", "c", 1)


if __name__ == "__main__":
    unittest.main()
