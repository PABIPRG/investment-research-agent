import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from huohuo.contracts import Invalid
from huohuo.market.source_transitions import record_source_transition

SQL = Path(__file__).resolve().parents[1] / "sidecar/huohuo/market/015_source_heads.sql"
LEGACY = "CREATE TABLE source_versions(event_id TEXT PRIMARY KEY,principal TEXT NOT NULL,subject TEXT NOT NULL,scope_key TEXT NOT NULL,source TEXT NOT NULL,version TEXT NOT NULL,document TEXT NOT NULL,observed_at TEXT NOT NULL,UNIQUE(principal,scope_key,source,version))"


class SourceTransitionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="market-transition-test-")
        self.path = Path(self.tmp.name) / "business.sqlite"
        self.db = self.connect()
        self.db.execute(LEGACY)
        self.migrate()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def migrate(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for statement in SQL.read_text().split(";"):
                if statement.strip():
                    self.db.execute(statement)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def record(self, version, *, db=None, principal="alice", key="scope1", stamp="2026-10-27T08:00:00+00:00"):
        db = db or self.db
        return record_source_transition(db, principal=principal, scope_key=key, entity_id="SEC:CN:A:600519",
                                        source="market:market_quote", version=version, document={"price_version": version}, observed_at=stamp)

    def commit(self, version, **kwargs):
        self.db.execute("BEGIN IMMEDIATE")
        result = self.record(version, **kwargs)
        self.db.commit()
        return result

    def test_adjacent_duplicates_and_round_trip_are_distinct(self):
        a, changed = self.commit("A")
        self.assertTrue(changed)
        self.assertEqual(self.commit("A"), (a, False))
        b, _ = self.commit("B")
        a2, _ = self.commit("A")
        self.assertEqual(len({a, b, a2}), 3)
        self.assertEqual(self.commit("A"), (a2, False))
        docs = self.db.execute("SELECT document FROM source_versions ORDER BY rowid").fetchall()
        self.assertEqual([json.loads(r[0])["price_version"] for r in docs], ["A", "B", "A"])

    def test_heads_survive_restart_and_do_not_depend_on_wall_clock_order(self):
        first, _ = self.commit("A")
        second, _ = self.commit("B", stamp="2026-10-26T08:00:00+00:00")
        self.db.close()
        self.db = self.connect()
        self.assertEqual(self.commit("B"), (second, False))
        third, _ = self.commit("A")
        self.assertNotEqual(first, third)

    def test_failure_rolls_back_snapshot_and_head_together(self):
        old, _ = self.commit("A")
        self.db.execute("BEGIN IMMEDIATE")
        discarded, _ = self.record("B")
        # 模拟同事务 record_event 失败。
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT event_id FROM source_heads").fetchone()[0], old)
        self.assertIsNone(self.db.execute("SELECT 1 FROM source_versions WHERE event_id=?", (discarded,)).fetchone())
        self.assertEqual(self.commit("B"), (discarded, True))

    def test_concurrent_same_state_creates_one_snapshot(self):
        self.commit("A")
        barrier = threading.Barrier(2)
        def run():
            db = self.connect()
            try:
                barrier.wait(timeout=3)
                db.execute("BEGIN IMMEDIATE")
                result = self.record("B", db=db)
                db.commit()
                return result
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            values = [future.result() for future in futures]
        self.assertEqual(values[0][0], values[1][0])
        self.assertEqual(sum(changed for _, changed in values), 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM source_versions").fetchone()[0], 2)

    def test_scope_and_principal_are_isolated_and_transaction_required(self):
        with self.assertRaises(Invalid):
            self.record("A")
        a, _ = self.commit("A")
        b, _ = self.commit("A", principal="bob")
        c, _ = self.commit("A", key="scope2")
        self.assertEqual(len({a, b, c}), 3)

    def test_upgrade_keeps_old_ids_documents_and_seeds_latest_head(self):
        self.db.close()
        self.path = Path(self.tmp.name) / "legacy.sqlite"
        self.db = self.connect()
        self.db.execute(LEGACY)
        for event, version, stamp in [("old-a", "A", "2026-10-26T08:00:00+00:00"), ("old-b", "B", "2026-10-27T08:00:00+00:00")]:
            self.db.execute("INSERT INTO source_versions VALUES(?,?,?,?,?,?,?,?)",
                            (event, "alice", "SEC:CN:A:600519", "scope1", "market:market_quote", version, '{"original":true}', stamp))
        self.migrate()
        self.assertEqual(self.commit("B"), ("old-b", False))
        new, changed = self.commit("A")
        self.assertTrue(changed)
        self.assertNotEqual(new, "old-a")
        self.assertEqual(self.db.execute("SELECT document FROM source_versions WHERE event_id='old-a'").fetchone()[0], '{"original":true}')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM source_versions").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
