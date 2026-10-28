"""真实升级前 schema 的合成实例；不读取旧用户数据。"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.contracts import canonical
from huohuo.strategies.service import Strategies
from huohuo.strategies.schedule import DEFAULT
from huohuo.strategies.validation import definition
from huohuo.research_partner.adapters import sqlite_store


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.now=datetime(2025,10,6,9,1,tzinfo=timezone.utc).timestamp()
        old=self.root/'old-sql';old.mkdir()
        for f in sqlite_store._MIGRATIONS_DIR.glob('*.sql'):
            if f.name<'017':(old/f.name).write_bytes(f.read_bytes())
        self.path=self.root/'business.sqlite';self.repo=Repository(self.path,clock=lambda:self.now)
        with patch.object(sqlite_store,'_MIGRATIONS_DIR',old):self.core=Mandates(self.repo,'upgrade-test')
        self.db=self.core.store._connect()
        self.strategy=definition({'name':'合成旧策略','kind':'momentum','params':{'n':5},'securities':[{'code':'600519','name':'贵州茅台'}],'direction':'利好','rationale':'合成升级测试'})
        self.strategy.update(revision=1,status='candidate',backtest={})
        self.db.execute('INSERT INTO strategy_documents VALUES(?,?,?,?)',('alice','strategies',self.strategy['id'],canonical(self.strategy)))
        self.policy={**DEFAULT,'revision':4,'enabled':True,'strategy_ids':[self.strategy['id']],'actions':['backtest','shadow']}
    def tearDown(self):self.core.store.close();self.tmp.cleanup()
    def seed(self,confirmed=True):
        self.db.execute('INSERT INTO strategy_schedules VALUES(?,?,?,?,?,?)',('alice',4,1,canonical(self.policy),self.now+86400,self.now))
        if confirmed:
            self.db.execute('INSERT INTO strategy_previews VALUES(?,?,?,?,?,?,?,?,?,?,?)',('spv','alice','synthetic','key','fp','schedule',canonical({'command':{**self.policy,'revision':3},'summary':'合成已确认计划'}),'v1',self.now+10,'committed',canonical({'run':{'status':'completed'},'automation':self.policy})))
    def job(self,jid,action,status):
        self.db.execute('INSERT INTO strategy_background_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(jid,'alice',4,'2025-10-06',self.strategy['id'],action,status,None,self.now,self.now,None,None))
    def reopen(self):
        self.core.store.close();self.repo=Repository(self.path,clock=lambda:self.now);self.core=Mandates(self.repo,'upgrade-test')
        self.api=Strategies(self.core.store,clock=lambda:self.now)
        self.db=self.core.store._connect()
    def test_pending_import_once_running_interrupted_and_archives_frozen(self):
        self.seed();self.job('old-pending','shadow','pending');self.job('old-running','backtest','running')
        self.reopen()
        view=self.api.read('alice');self.assertTrue(view['automation']['enabled']);self.assertEqual(view['automation']['revision'],1)
        self.assertEqual({r['status'] for r in view['background_jobs']},{'pending','interrupted'})
        self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM attempts').fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM attempts WHERE status='running'").fetchone()[0],0)
        self.assertTrue(self.path.with_suffix('.sqlite.before-unified-strategy').exists())
        with self.assertRaises(Exception):self.db.execute("UPDATE legacy_strategy_background_jobs SET status='pending'")
        self.reopen();self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],2)
        self.assertEqual(len(self.api.read('alice')['background_jobs']),2)
    def test_no_confirmation_stays_paused_and_no_pending_work_reactivated(self):
        self.seed(confirmed=False);self.job('old-pending','backtest','pending');self.reopen()
        self.assertFalse(self.api.read('alice')['automation']['enabled'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],0)
        self.assertEqual(self.api.read('alice')['background_jobs'][0]['status'],'cancelled')
    def test_old_terminal_rows_remain_history_not_fake_executions(self):
        self.seed();self.job('old-done','backtest','completed');self.reopen()
        self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],0)
        self.assertEqual(self.api.read('alice')['background_jobs'][0]['id'],'old-done')
        self.assertTrue(self.api.read('alice')['background_jobs'][0]['archived'])
        self.core.tick();self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],0)
    def test_failed_data_mapping_rolls_back_and_restart_retries_without_duplicates(self):
        self.seed();self.job('old-pending','backtest','pending')
        with patch('huohuo.research_partner.strategy_tasks.StrategyTasks.enqueue',side_effect=RuntimeError('synthetic migration interruption')):
            with self.assertRaises(RuntimeError):self.reopen()
        self.db=self.core.store._connect()
        self.assertEqual(self.db.execute('SELECT count(*) FROM mandate_workflows').fetchone()[0],0)
        self.assertIsNone(self.db.execute("SELECT 1 FROM meta WHERE key='strategy_core_upgrade_v1'").fetchone())
        self.reopen();self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],1)

    def test_consumed_slot_dedupes_even_when_old_due_cursor_is_stale(self):
        self.seed();self.job('old-done','backtest','completed');self.job('old-pending','shadow','pending')
        self.db.execute('UPDATE strategy_schedules SET next_at=?',(self.now-60,))
        self.reopen();self.core.tick()
        self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM research_jobs WHERE action='strategy.backtest' AND status='completed'").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM research_jobs WHERE action='baseline_review'").fetchone()[0],0)

    def test_all_terminal_slots_remain_visible_and_never_replay(self):
        self.policy['actions']=['backtest','shadow','evolve'];self.policy['archive_recall']=True
        self.seed()
        states={'backtest':'completed','shadow':'skipped','evolve':'failed','recall':'cancelled'}
        for action,state in states.items():
            self.job('old-'+action,action,state)
            if action=='recall':self.db.execute("UPDATE strategy_background_jobs SET strategy_id='strategy_pool' WHERE id=?",('old-'+action,))
        self.db.execute('UPDATE strategy_schedules SET next_at=?',(self.now-60,))
        self.reopen();self.core.tick();self.reopen();self.core.tick()
        self.assertEqual(self.db.execute('SELECT count(*) FROM executions').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM attempts').fetchone()[0],0)
        self.assertEqual({r['action']:r['status'] for r in self.api.read('alice')['background_jobs']},states)
