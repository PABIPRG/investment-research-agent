"""策略持续工作必须由核心委托和统一执行链持有。"""
import json
import unittest
import test_strategy_background as fixtures


class UnifiedStrategyTests(unittest.TestCase):
    setUp=fixtures.BackgroundTests.setUp
    tearDown=fixtures.BackgroundTests.tearDown
    command=fixtures.BackgroundTests.command
    create=fixtures.BackgroundTests.create
    plan=fixtures.BackgroundTests.plan
    ready=fixtures.BackgroundTests.ready
    event=fixtures.BackgroundTests.event
    drain=fixtures.BackgroundTests.drain
    def test_plan_and_background_have_core_execution_binding(self):
        self.ready(actions=['backtest'])
        view = self.api.read('alice')
        self.assertIn('mandate_id', view['automation'])
        result = self.api.background_tick('alice')
        db = self.core.store._connect()
        row = db.execute('SELECT e.*,x.job_id,a.status AS attempt_status FROM executions e JOIN execution_jobs x ON x.execution_id=e.id JOIN attempts a ON a.id=e.current_attempt WHERE x.mandate_id=?', (view['automation']['mandate_id'],)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['status'], 'succeeded')
        self.assertEqual(row['attempt_status'], 'succeeded')
        self.assertEqual(result['run']['execution_id'], row['id'])
        self.assertEqual(json.loads(row['scope'])['kind'], 'strategy')

    def test_candidate_uses_same_attempt_and_runtime_receipt(self):
        self.ready(event_candidates=True)
        self.api.ingest_events('alice', [self.event()])
        job = self.api.planner_claim('alice', 'worker')
        self.assertIn('attempt_id', job)
        self.repo.runtime_receipt(job['attempt_id'], job['lease_token'], {'session_id':'synthetic-session','message_id':'synthetic-message'})
        self.api.planner_finish('alice', job['job_id'], job['lease_token'], {'status':'completed','candidates':[]})
        self.assertEqual(self.repo.get('alice', job['execution_id'])['status'], 'succeeded')
        self.assertEqual(self.api.read('alice')['suggestions'], [])

    def test_typed_plan_never_creates_financial_baseline(self):
        s=self.create(); self.plan(enabled=True,strategy_ids=[s['id']])
        self.core.tick()
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM executions').fetchone()[0],0)
        self.assertEqual(self.api.background_tick('alice')['status'],'idle')
        self.assertEqual(self.core.list('alice')['items'],[])

    def test_generic_execution_cannot_forge_strategy_scope(self):
        from huohuo.contracts import Invalid
        self.ready(); self.core.tick()
        row=self.core.store._connect().execute('SELECT scope FROM executions LIMIT 1').fetchone()
        with self.assertRaises(Invalid):self.repo.create('alice','forged',json.loads(row[0]),'forged')

    def test_same_queue_no_duplicate_claim_and_expiry_reconciles_job(self):
        self.ready(actions=['backtest'])
        job=self.api.tasks.claim('alice','one')
        self.assertIsNone(self.api.tasks.claim('alice','two'))
        self.assertIsNone(self.repo.claim('stock-worker'))
        self.now+=31;self.repo.recover()
        self.assertEqual(self.repo.get('alice',job['execution_id'])['status'],'interrupted')
        self.assertEqual(self.core.store.get_job(job['job_id']).status,'failed')
        self.assertIsNone(self.api.tasks.claim('alice','three'))

    def test_domain_and_execution_completion_rollback_together(self):
        from unittest.mock import patch
        from huohuo.execution import Conflict
        s=self.ready(actions=['backtest'])
        with patch.object(self.repo,'finish',side_effect=Conflict('synthetic lost capability')):
            result=self.api.background_tick('alice')
        self.assertEqual(self.api.read('alice')['strategies'][0]['status'],'candidate')
        db=self.core.store._connect()
        self.assertEqual(db.execute('SELECT count(*) FROM strategy_run_evidence').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT count(*) FROM result_outbox').fetchone()[0],0)
        self.now+=31;self.repo.recover()
        self.assertEqual(self.api.read('alice')['background_jobs'][0]['status'],'interrupted')

    def test_cancel_one_run_keeps_plan_active(self):
        self.ready(actions=['backtest','evolve']); old=self.api.history
        def cancel(*args):
            run=next(r for r in self.api.read('alice')['runs'] if r['status']=='running')
            self.api.cancel('alice',{'run_id':run['id']})
            return old(*args)
        self.api.history=cancel
        result=self.api.background_tick('alice')
        self.assertEqual(result['run']['status'],'cancelled')
        self.assertTrue(self.api.read('alice')['automation']['enabled'])
        self.assertEqual(self.repo.get('alice',result['run']['execution_id'])['status'],'cancelled')
        self.assertIsNotNone(self.api.tasks.claim('alice','next'))

    def test_candidate_repeat_conflict_and_scope_enforcement(self):
        from huohuo.execution import Conflict
        self.ready(event_candidates=True);self.api.ingest_events('alice',[self.event()])
        job=self.api.planner_claim('alice','worker')
        self.api.planner_finish('alice',job['job_id'],job['lease_token'],{'status':'completed','candidates':[]})
        with self.assertRaises(Conflict):self.api.planner_finish('alice',job['job_id'],job['lease_token'],{'status':'failed','error':'changed'})
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM contact_decisions').fetchone()[0],0)
        self.assertEqual(self.core.store._connect().execute("SELECT count(*) FROM domain_events WHERE hook_type='strategy.source'").fetchone()[0],1)

    def test_live_lease_survives_normal_recovery_but_restart_interrupts(self):
        self.ready(actions=['backtest']);job=self.api.tasks.claim('alice','worker')
        self.repo.recover()
        self.assertEqual(self.repo.get('alice',job['execution_id'])['status'],'running')
        self.repo.recover(abandoned=True)
        self.assertEqual(self.repo.get('alice',job['execution_id'])['status'],'interrupted')
        self.assertIsNone(self.api.tasks.claim('alice','worker'))

    def test_calculation_receipt_replayed_without_recomputing(self):
        self.ready(actions=['backtest'])
        job=self.api.tasks.claim('alice','worker')
        from huohuo.strategies.background import run
        one=run(self.api,'alice',job['job_id'],job['lease_token'])
        count=len(self.calls)
        self.assertEqual(run(self.api,'alice',job['job_id'],job['lease_token']),one)
        self.assertEqual(len(self.calls),count)
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM result_outbox').fetchone()[0],1)

    def test_multiple_strategies_backtest_before_shadow_before_evolve(self):
        first=self.create();self.candidate['name']='第二个合成策略';self.candidate['params']={'n':8};second=self.create()
        self.plan(enabled=True,strategy_ids=[first['id'],second['id']],actions=['backtest','shadow','evolve'])
        self.now+=3601
        result=self.drain()
        actions=[r['run']['action'] for r in result if 'run' in r]
        self.assertEqual(actions,['backtest','backtest','shadow','shadow','evolve','evolve'])
