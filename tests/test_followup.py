"""明确合成来源；真实 SQLite/领域服务，绝不对外发送。"""
import json
import threading
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.research_entities.bounded import collect
from huohuo.research import snapshot
from huohuo.research_partner.router import EventRouter
from huohuo.research_partner.models import EventEnvelope

SCOPE={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'financial_summary','period':'20260630','metric':'营业总收入','basis':'source_abstract'}
QUOTE_SCOPE={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'}
PROFILE_SCOPE={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'company_profile'}
class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.scope=SCOPE
        self.tmp=tempfile.TemporaryDirectory();self.repo=Repository(Path(self.tmp.name)/'business.sqlite');self.core=Mandates(self.repo,'test')
        self.core.entities.directory=lambda:{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'fixture'}}
    def tearDown(self):self.core.store.close();self.tmp.cleanup()
    def create(self,principal='alice',key='create-first',**extra):
        r=self.core.entities.resolve(principal,'test','600519');c=self.core.entities.confirm(principal,'test',r['snapshot_id'],r['version'],{r['mentions'][0]['mention_id']:SCOPE['entity_id']},'fixture')
        return self.core.create(principal,{'session_id':'test','confirmation_id':c['confirmations'][0]['confirmation_id'],'request_key':key,'goal':'合成验收：跟进已确认范围变化','scope':self.scope,'contact_note':'仅应用内',**extra})
    def document(self,value=100):
        if self.scope['operation']=='quote_snapshot':
            return snapshot(self.scope,lambda _: ({'data':{'diff':[{'f12':'600519','f2':value,'f18':99,'f124':int(self.repo.clock())}]}},'https://example.invalid/quote'))
        if self.scope['operation']=='company_profile':
            return collect(PROFILE_SCOPE,lambda _: {'code':'600519','records':[{'公司名称':'贵州茅台','主营业务':'白酒'}]})
        return collect(SCOPE,lambda _: {'code':'600519','records':[{'指标':'营业总收入','20260630':value}]})
    def result(self,verdict=None,fail=False):
        job=self.repo.claim('test-worker');self.assertIsNotNone(job)
        verdict=verdict or ('unknown' if self.scope['operation']=='financial_summary' else 'met')
        if fail:self.repo.finish(job['attempt_id'],job['lease_token'],{'status':'failed','error':'合成来源失败'})
        else:
            ev=self.repo.save_evidence(job['attempt_id'],job['lease_token'],self.document())
            self.repo.finish(job['attempt_id'],job['lease_token'],{'status':'succeeded','execution_id':job['execution_id'],'scope':self.scope,'summary':'合成验收研究结果','evidence_ids':[ev['evidence_id']],'judgements':{'notable_change':{'judgement':verdict,'reason':'合成证据比较','evidence_refs':[ev['evidence_id']]}}})
        self.core.tick()
    def enable(self):return self.core.notifications.save('alice',{'expected_revision':0,'enabled':True,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':None})
    def jobs(self):return self.core.store._connect().execute('SELECT * FROM research_jobs').fetchall()
    def test_failed_baseline_blocks_reviews_until_explicit_retry(self):
        self.core.sources.accept('alice',self.document(101));m=self.create();self.core.tick()
        self.result(fail=True)
        reviews=[r for r in self.jobs() if r['action']=='event_review']
        self.assertTrue(reviews and all(r['status']=='pending' for r in reviews))
        # 失败后没有派发任何执行：事件复核必须等基准成功。
        self.assertIsNone(self.repo.claim('probe'))
        current=self.core.get('alice',m['mandate']['mandate_id'])
        self.core.command('alice',m['mandate']['mandate_id'],'retry_baseline',{'request_key':'confirmed-retry','expected_revision':current['mandate']['current_revision'],'expected_generation':current['generation']})
        self.core.tick()
        retry=self.repo.claim('probe');self.assertIsNotNone(retry);self.assertIn('baseline_review',retry['question'])
        self.assertIsNone(self.repo.claim('probe-2'))
        ev=self.repo.save_evidence(retry['attempt_id'],retry['lease_token'],self.document())
        self.repo.finish(retry['attempt_id'],retry['lease_token'],{'status':'succeeded','execution_id':retry['execution_id'],'scope':self.scope,'summary':'基准重试成功','evidence_ids':[ev['evidence_id']]})
        self.core.tick()
        self.assertEqual(self.core.get('alice',m['mandate']['mandate_id'])['baseline']['summary'],'基准重试成功')

    def test_source_duplicate_correction_and_principal_isolation(self):
        self.create();self.create('bob');self.core.tick()
        first=self.core.sources.accept('alice',self.document());self.assertEqual(first,self.core.sources.accept('alice',self.document()))
        self.core.tick();reviews=[r for r in self.jobs() if r['action']=='event_review'];self.assertEqual(len(reviews),1)
        self.core.sources.accept('alice',self.document(101));self.core.tick();self.assertEqual(len([r for r in self.jobs() if r['action']=='event_review']),2)
        self.assertNotEqual(first,self.core.sources.accept('alice',self.document(102)))
    def test_source_before_subscription_catches_up(self):
        self.core.sources.accept('alice',self.document());self.core.tick();self.create();self.core.tick()
        self.assertEqual(len([r for r in self.jobs() if r['action']=='event_review']),1)
    def test_concurrent_creation_and_source_never_misses(self):
        barrier=threading.Barrier(2);errors=[]
        def source():
            try:barrier.wait();self.core.sources.accept('alice',self.document())
            except Exception as e:errors.append(e)
        t=threading.Thread(target=source);t.start();barrier.wait();self.create();t.join();self.core.tick()
        self.assertEqual(errors,[]);self.assertEqual(len([r for r in self.jobs() if r['action']=='event_review']),1)
    def test_archive_does_not_trigger_source_dependency(self):
        self.create();self.core.tick();before=len(self.jobs());now=datetime.now(timezone.utc)
        self.core.store.record_event(EventEnvelope(event_id='archive-test',hook_type='research.run_completed',producer='test',occurred_at=now,observed_at=now,subject_ids=[SCOPE['entity_id']],payload={}))
        self.core.tick();self.assertEqual(len(self.jobs()),before)
    def test_true_false_unknown_failure_distinct_and_no_default_auto_cost(self):
        # 条件/投递机制用单位明确的报价；未知财务口径的拒绝另由准入回归覆盖。
        self.scope=QUOTE_SCOPE;self.enable();views=[]
        for index,verdict in enumerate(['met','unmet','unknown','failed']):
            m=self.create(key='condition-'+str(index));self.core.tick()
            self.result(verdict,fail=verdict=='failed')
            views.append(self.core.get('alice',m['mandate']['mandate_id']))
        self.assertEqual({d['condition_result'] for v in views for d in v['decisions']},{'met','unmet','unknown','error'})
        self.assertFalse(any(r['action']=='condition_retry' for r in self.jobs()))
        notifications=[n for v in views for n in v['notifications']]
        self.assertEqual(len(notifications),1);self.assertEqual(notifications[0]['status'],'delivered')
    def prepare_queue(self):
        self.scope=QUOTE_SCOPE;self.enable();m=self.create();self.core.tick()
        tick=self.core.notifications.tick;self.core.notifications.tick=lambda:None
        self.result();self.core.notifications.tick=tick
        return m,self.core.notifications.list('alice')['items'][0]
    def test_pause_before_send_blocks(self):
        m,q=self.prepare_queue();self.core.command('alice',m['mandate']['mandate_id'],'pause',{'request_key':'pause-once','expected_revision':1,'expected_generation':0})
        self.assertIsNone(self.core.notifications.reserve(q['decision_id']));self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'],'cancelled')
    def test_send_before_pause_is_in_flight_not_recalled(self):
        m,q=self.prepare_queue();permit=self.core.notifications.reserve(q['decision_id']);self.assertIsNotNone(permit)
        self.core.command('alice',m['mandate']['mandate_id'],'pause',{'request_key':'pause-once','expected_revision':1,'expected_generation':0})
        self.core.notifications.settle(permit,'accepted','渠道受理');self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'],'accepted')
    def test_concurrent_pause_and_send_linearize(self):
        m,q=self.prepare_queue();barrier=threading.Barrier(2);permits=[];errors=[]
        def reserve():
            try:barrier.wait();permits.append(self.core.notifications.reserve(q['decision_id']))
            except Exception as e:errors.append(e)
        t=threading.Thread(target=reserve);t.start();barrier.wait();self.core.command('alice',m['mandate']['mandate_id'],'pause',{'request_key':'pause-once','expected_revision':1,'expected_generation':0});t.join()
        self.assertEqual(errors,[]);self.assertIn(self.core.notifications.list('alice')['items'][0]['status'],['cancelled','in_flight']);self.assertIsNone(self.core.notifications.reserve(q['decision_id']))
    def test_config_disable_and_ttl_block(self):
        _,q=self.prepare_queue();self.core.notifications.save('alice',{'expected_revision':1,'enabled':False,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':None})
        self.assertIsNone(self.core.notifications.reserve(q['decision_id']))
    def test_unknown_not_replayed_and_crash_recovery(self):
        _,q=self.prepare_queue();permit=self.core.notifications.reserve(q['decision_id']);self.core.notifications.settle(permit,'unknown','失去回执');self.core.notifications.tick()
        self.assertIsNone(self.core.notifications.reserve(q['decision_id']));self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'],'unknown')
    def test_decision_and_queue_atomic_rollback(self):
        self.scope=QUOTE_SCOPE;self.enable();self.create();self.core.tick();job=self.repo.claim('test');ev=self.repo.save_evidence(job['attempt_id'],job['lease_token'],self.document())
        self.repo.finish(job['attempt_id'],job['lease_token'],{'status':'succeeded','execution_id':job['execution_id'],'scope':self.scope,'summary':'test','evidence_ids':[ev['evidence_id']],'judgements':{'notable_change':{'judgement':'met','evidence_refs':[ev['evidence_id']]}}})
        with self.core.store.transaction():self.core.store._connect().execute("CREATE TRIGGER fail_queue BEFORE INSERT ON notification_queue BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(Exception):self.core.tick()
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM contact_decisions').fetchone()[0],0)
        with self.core.store.transaction():self.core.store._connect().execute('DROP TRIGGER fail_queue')
        self.core.tick();self.assertEqual(len(self.core.notifications.list('alice')['items']),1)
    def test_investment_event_contract_idempotency_and_conflict(self):
        ev={'event_id':'fact-1','subject_ids':[SCOPE['entity_id']],'fact_version':'1','change_type':'trade.corrected'}
        self.assertTrue(self.core.accept_investment_event('alice',ev));self.assertFalse(self.core.accept_investment_event('alice',ev))
        with self.assertRaises(Exception):self.core.accept_investment_event('alice',ev|{'fact_version':'2'})
    def test_source_content_pinned_to_execution(self):
        self.create();self.core.tick();self.result('unknown')
        event=self.core.sources.accept('alice',self.document(123));self.core.tick()
        self.core.sources.accept('alice',self.document(456))
        job=self.repo.claim('test');doc=self.core.bound_source(job['execution_id'])
        self.assertEqual(doc['values']['records'][0]['20260630'],123)
    def test_quiet_ends_only_rechecks_delivery(self):
        _,q=self.prepare_queue();clock=self.repo.clock();self.core.notifications.save('alice',{'expected_revision':1,'enabled':True,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':{'start':'00:00','end':'00:00'}})
        self.assertIsNone(self.core.notifications.reserve(q['decision_id']));self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'],'deferred')
        self.core.notifications.save('alice',{'expected_revision':2,'enabled':True,'channels':['app'],'timezone':'Asia/Shanghai','quiet_hours':None})
        with self.core.store.transaction():self.core.store._connect().execute('UPDATE notification_queue SET eligible_at=? WHERE decision_id=?',(clock-1,q['decision_id']))
        count=len(self.jobs());self.core.notifications.tick();self.assertEqual(len(self.jobs()),count);self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'],'delivered')
    def test_expiry_and_inflight_timeout(self):
        _,q=self.prepare_queue();original=self.repo.clock;self.repo.clock=lambda:original()+86401
        self.assertIsNone(self.core.notifications.reserve(q['decision_id']));self.assertEqual(self.core.notifications.list('alice')['items'][0]['status'],'cancelled')
    def test_due_reminder_without_dsh_does_not_invent_research(self):
        self.enable();m=self.create();mid=m['mandate']['mandate_id']
        self.core.command('alice',mid,'revise',{'request_key':'daily-reminder','expected_revision':1,'expected_generation':0,'goal':m['revision']['goal'],'scope':SCOPE,'contact_note':'每天9点提醒','reminder_time':'09:00'})
        self.core.tick()
        with self.core.store.transaction():self.core.store._connect().execute("UPDATE mandate_schedules SET next_due_at=?",(datetime.now(timezone.utc).isoformat(),))
        self.core.tick();view=self.core.get('alice',mid)
        reminders=[r for r in self.jobs() if r['action']=='due_reminder'];self.assertEqual(len(reminders),1);self.assertEqual(reminders[0]['status'],'completed')
        self.assertTrue(any(d['reason_code']=='due_reminder' for d in view['decisions']))
        self.assertTrue(any(r['structured_result'].get('kind')=='explicit_due_reminder' for r in view['results']))
    def test_company_profile_discovery_emits_versioned_event(self):
        self.scope=PROFILE_SCOPE
        view=self.create();mid=view['mandate']['mandate_id']
        self.assertTrue(self.core.get('alice',mid)['monitoring']['enabled'])
        document=collect(PROFILE_SCOPE,lambda _: {'code':'600519','records':[{'公司名称':'贵州茅台','主营业务':'白酒'}]})
        result=self.core.sources.discover(lambda _: document)
        self.assertEqual(result['status'],'ok')
        db=self.core.store._connect()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM source_versions').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT hook_type FROM domain_events').fetchone()[0],'company.profile_changed')
        self.core.tick();self.result()
        changed=collect(PROFILE_SCOPE,lambda _: {'code':'600519','records':[{'公司名称':'贵州茅台','主营业务':'白酒、金融'}]})
        with self.core.store.transaction():self.core.store._connect().execute('UPDATE source_checks SET checked_at=checked_at-21700')
        self.assertEqual(self.core.sources.discover(lambda _: changed)['status'],'ok')
        self.core.tick()
        self.assertTrue(any(r['action']=='event_review' for r in self.jobs()))
    def test_quote_discovery_emits_versioned_event_only_when_price_changes(self):
        self.scope=QUOTE_SCOPE
        self.core.repo.clock=lambda: datetime(2026,10,26,10,0,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        from types import SimpleNamespace
        self.core.service.calendar=SimpleNamespace(is_trading_day=lambda day:True)
        view=self.create(key='quote-discovery')
        self.assertTrue(view['monitoring']['enabled'])
        self.assertEqual(self.core.sources.discover(lambda _: self.document(100))['status'],'ok')
        db=self.core.store._connect()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM source_versions').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT hook_type FROM domain_events').fetchone()[0],'quote.snapshot_changed')
        with self.core.store.transaction():db.execute('UPDATE source_checks SET checked_at=checked_at-901')
        self.assertEqual(self.core.sources.discover(lambda _: self.document(100))['status'],'ok')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM source_versions').fetchone()[0],1)
        with self.core.store.transaction():db.execute('UPDATE source_checks SET checked_at=checked_at-901')
        self.assertEqual(self.core.sources.discover(lambda _: self.document(97))['status'],'ok')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM source_versions').fetchone()[0],2)
    def test_quote_discovery_skips_outside_trading_session(self):
        self.scope=QUOTE_SCOPE
        self.core.repo.clock=lambda: datetime(2026,10,26,12,0,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        self.create(key='quote-lunch')
        self.assertFalse(self.core.sources.discover(lambda _: self.document(100)).get('checked'))
        self.assertEqual(self.core.store._connect().execute('SELECT COUNT(*) FROM source_versions').fetchone()[0],0)
    def test_numeric_quote_condition_uses_program_metrics(self):
        self.scope=QUOTE_SCOPE
        view=self.create(key='quote-numeric',contact_condition={'type':'numeric','metric':'price','operator':'<=','threshold':98})
        mid=view['mandate']['mandate_id']
        self.core.tick();self.result()
        self.core.sources.accept('alice',self.document(95));self.core.tick();self.core.tick()
        job=self.repo.claim('test-worker');self.assertIsNotNone(job)
        ev=self.repo.save_evidence(job['attempt_id'],job['lease_token'],self.document(95))
        # 模型结果不含任何数字；判定只使用程序从来源快照读到的价格。
        self.repo.finish(job['attempt_id'],job['lease_token'],{'status':'succeeded','execution_id':job['execution_id'],'scope':self.scope,'summary':'报价复核','evidence_ids':[ev['evidence_id']]})
        self.core.tick()
        decisions=self.core.get('alice',mid)['decisions']
        self.assertTrue(any(d['condition_result']=='met' for d in decisions))
    def test_failed_source_no_success_event(self):
        self.create();self.core.sources.discover(lambda _: {'status':'unavailable','reason':'period_not_covered','scope':SCOPE})
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM source_versions').fetchone()[0],0)
        self.assertEqual(self.core.store._connect().execute('SELECT status FROM source_checks').fetchone()[0],'unavailable')
    def test_external_events_wait_for_baseline_and_never_replace_it(self):
        self.core.sources.accept('alice',self.document(101));m=self.create();self.core.tick()
        claim=self.repo.claim('test');self.assertIn('baseline_review',claim['question']);self.assertIsNone(self.repo.claim('second'))
        ev=self.repo.save_evidence(claim['attempt_id'],claim['lease_token'],self.document())
        self.repo.finish(claim['attempt_id'],claim['lease_token'],{'status':'succeeded','execution_id':claim['execution_id'],'scope':SCOPE,'summary':'固定初次基准','evidence_ids':[ev['evidence_id']]})
        self.core.tick();self.core.tick();self.result()
        self.assertEqual(self.core.get('alice',m['mandate']['mandate_id'])['baseline']['summary'],'固定初次基准')
