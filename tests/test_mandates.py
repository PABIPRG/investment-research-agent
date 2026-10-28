import tempfile
import unittest
from pathlib import Path
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.research import snapshot

SCOPE = {'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'}

class MandateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name)/'business.sqlite')
        self.core = Mandates(self.repo, 'test-instance')
        self.core.entities.directory=lambda:{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'}],'source':{'provider':'fixture'}}
        r=self.core.entities.resolve('alice','test-chat','600519')
        receipt=self.core.entities.confirm('alice','test-chat',r['snapshot_id'],r['version'],{r['mentions'][0]['mention_id']:SCOPE['entity_id']},'fixture-answer')
        self.confirmation=receipt['confirmations'][0]['confirmation_id']
    def tearDown(self):
        self.core.store.close()
        self.tmp.cleanup()
    def create(self):
        return self.core.create('alice', {'session_id':'test-chat','confirmation_id':self.confirmation,'request_key':'create-001','goal':'明确委托：研究当前报价','scope':SCOPE,'contact_note':'仅在产品中查看'})
    def complete(self, job):
        ev=self.repo.save_evidence(job['attempt_id'],job['lease_token'],snapshot(SCOPE,lambda _:({'data':{'diff':[{'f12':'600519','f2':10,'f18':11,'f124':int(self.repo.clock())}]}},'https://example.invalid/quote')))
        result={'status':'succeeded','execution_id':job['execution_id'],'scope':SCOPE,'summary':'测试来源的报价','evidence_ids':[ev['evidence_id']]}
        self.repo.finish(job['attempt_id'],job['lease_token'],result)
        return result
    def test_etf_quote_mandate_is_supported(self):
        # 使用内置已确认证券目录；保持 canonical 基金身份并映射到执行身份。
        r=self.core.entities.resolve('alice','etf-chat','510300')
        eid=next(c['entity_id'] for c in r['mentions'][0]['candidates'] if c['entity_type_code']=='ENTITY_01_02')
        receipt=self.core.entities.confirm('alice','etf-chat',r['snapshot_id'],r['version'],{r['mentions'][0]['mention_id']:eid},'fixture-answer')
        confirmation=receipt['confirmations'][0]
        self.assertEqual(confirmation['operations'],['quote_snapshot'])
        scope={'entity_id':confirmation['execution_entity_id'],'exchange':confirmation['exchange'],'operation':'quote_snapshot'}
        view=self.core.create('alice',{'session_id':'etf-chat','confirmation_id':confirmation['confirmation_id'],'request_key':'etf-create-001','goal':'跟踪已确认ETF报价','scope':scope,'contact_note':'仅应用内'})
        self.assertEqual(view['revision']['scope']['entity_id'],'FUND:CN:510300')
        self.core.tick();self.assertIsNotNone(self.repo.claim('worker'))

    def test_event_chain_and_crash_before_core_receive(self):
        m=self.create(); self.assertEqual(m['mandate']['mandate_id'],self.create()['mandate']['mandate_id'])
        self.core.tick()
        job=self.repo.claim('worker'); self.assertIsNotNone(job)
        result=self.complete(job)
        self.core.store.close(); self.core=Mandates(self.repo,'test-instance')
        self.core.tick(); view=self.core.get('alice',m['mandate']['mandate_id'])
        self.assertEqual(view['baseline']['summary'],result['summary'])
        self.core.tick(); self.assertEqual(len(self.core.get('alice',m['mandate']['mandate_id'])['results']),1)
        self.assertEqual(self.repo.finish(job['attempt_id'],job['lease_token'],result)['status'],'succeeded')
    def test_pause_resume_cannot_revive_attempt(self):
        m=self.create(); mid=m['mandate']['mandate_id'];self.core.tick();job=self.repo.claim('worker')
        m=self.core.command('alice',mid,'pause',{'request_key':'pause-001','expected_revision':1,'expected_generation':0})
        self.core.command('alice',mid,'resume',{'request_key':'resume-001','expected_revision':1,'expected_generation':m['generation']})
        with self.assertRaises(Conflict): self.complete(job)
    def test_failed_evidence_never_succeeds(self):
        self.create();self.core.tick();job=self.repo.claim('worker')
        ev=self.repo.save_evidence(job['attempt_id'],job['lease_token'],{'scope':SCOPE,'status':'error'})
        with self.assertRaises(Conflict): self.repo.finish(job['attempt_id'],job['lease_token'],{'status':'succeeded','execution_id':job['execution_id'],'scope':SCOPE,'summary':'bad','evidence_ids':[ev['evidence_id']]})
    def test_conflict_and_other_principal(self):
        m=self.create();mid=m['mandate']['mandate_id']
        with self.assertRaises(Exception):self.core.get('bob',mid)
        with self.assertRaises(Conflict):self.core.command('alice',mid,'pause',{'request_key':'pause-001','expected_revision':2,'expected_generation':0})
    def test_completed_before_pause_is_retained_but_stale(self):
        m=self.create();mid=m['mandate']['mandate_id'];self.core.tick();job=self.repo.claim('worker');self.complete(job)
        m=self.core.command('alice',mid,'pause',{'request_key':'pause-001','expected_revision':1,'expected_generation':0})
        self.core.command('alice',mid,'resume',{'request_key':'resume-001','expected_revision':1,'expected_generation':m['generation']})
        self.core.tick();view=self.core.get('alice',mid)
        self.assertIsNone(view['baseline']);self.assertTrue(view['results'][0]['stale'])
    def test_resume_schedules_new_attempt_when_baseline_missing(self):
        m=self.create();mid=m['mandate']['mandate_id'];self.core.tick();old=self.repo.claim('worker')
        m=self.core.command('alice',mid,'pause',{'request_key':'pause-001','expected_revision':1,'expected_generation':0})
        self.core.command('alice',mid,'resume',{'request_key':'resume-001','expected_revision':1,'expected_generation':m['generation']})
        self.core.tick();new=self.repo.claim('worker');self.assertIsNotNone(new);self.assertNotEqual(new['attempt_id'],old['attempt_id'])
    def test_cannot_retry_mandate_execution_via_single_quote_command(self):
        self.create();self.core.tick();job=self.repo.claim('worker')
        with self.assertRaises(Conflict):self.repo.command('alice',job['execution_id'],'cancel','other-command',job['revision'])
    def test_result_transaction_rolls_back_if_outbox_fails(self):
        self.create();self.core.tick();job=self.repo.claim('worker')
        with self.core.store.transaction():self.core.store._connect().execute("CREATE TRIGGER fail_result_outbox BEFORE INSERT ON result_outbox BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(Exception):self.complete(job)
        self.assertEqual(self.repo.get('alice',job['execution_id'])['status'],'running')
    def test_different_result_after_ack_is_conflict(self):
        self.create();self.core.tick();job=self.repo.claim('worker');result=self.complete(job)
        with self.assertRaises(Conflict):self.repo.finish(job['attempt_id'],job['lease_token'],result|{'summary':'different'})
    def test_contact_note_only_revision_does_not_research_again(self):
        m=self.create();mid=m['mandate']['mandate_id'];self.core.tick();job=self.repo.claim('worker');self.complete(job);self.core.tick()
        current=self.core.get('alice',mid)
        self.core.command('alice',mid,'revise',{'request_key':'revision-001','expected_revision':1,'expected_generation':0,'goal':current['revision']['goal'],'scope':SCOPE,'contact_note':'只改变备注'})
        self.core.tick();self.assertIsNone(self.repo.claim('worker'))
        self.assertEqual(self.core.get('alice',mid)['baseline_revision'],1)
    def test_semantic_contact_condition_is_persisted_and_given_to_worker(self):
        view=self.core.create('alice',{'session_id':'test-chat','confirmation_id':self.confirmation,'request_key':'condition-001','goal':'出现重组公告才联系','scope':SCOPE,'contact_note':'重组公告','contact_condition':{'claim':'公告出现重大资产重组'}})
        mid=view['mandate']['mandate_id']
        self.assertEqual(view['revision']['contact_policy']['condition']['claim'],'公告出现重大资产重组')
        self.assertTrue(view['revision']['contact_policy']['condition']['evidence_required'])
        self.core.tick();job=self.repo.claim('worker')
        self.assertIn('公告出现重大资产重组',job['question'])
    def test_numeric_contact_condition_is_rejected_instead_of_faked(self):
        from huohuo.contracts import Invalid
        with self.assertRaises(Invalid):
            self.core.create('alice',{'session_id':'test-chat','confirmation_id':self.confirmation,'request_key':'condition-002','goal':'跌破100元才联系','scope':SCOPE,'contact_note':'跌破100','contact_condition':{'type':'numeric','metric':'close','operator':'<','threshold':100}})
    def test_numeric_quote_condition_is_persisted_with_program_metrics(self):
        view=self.core.create('alice',{'session_id':'test-chat','confirmation_id':self.confirmation,'request_key':'condition-003','goal':'价格不高于1500元才联系','scope':SCOPE,'contact_note':'用户约定 price <= 1500','contact_condition':{'type':'numeric','metric':'price','operator':'<=','threshold':1500}})
        condition=view['revision']['contact_policy']['condition']
        self.assertEqual(condition['type'],'numeric')
        self.assertEqual(condition['unit'],'CNY/share')
        self.assertEqual(condition['basis_ref'],'用户明确约定')
        self.core.tick();job=self.repo.claim('worker')
        self.assertIn('"threshold":1500',job['question'])
    def test_numeric_condition_rejects_series_and_wrong_unit(self):
        from huohuo.contracts import Invalid
        from huohuo.research_partner.contact_rules import compile_rule, normalize_contact_input
        def contact_condition(value,operation):
            rule=normalize_contact_input({'contact_condition':value})['contact_rule']
            return compile_rule(rule,{'operation':operation},['app'])
        with self.assertRaises(Invalid):
            contact_condition({'type':'percentile','series':'close','operator':'<','threshold':0.1},'quote_snapshot')
        with self.assertRaises(Invalid):
            contact_condition({'type':'numeric','metric':'price','operator':'<','threshold':10,'unit':'%'},'quote_snapshot')
        with self.assertRaises(Invalid):
            contact_condition({'type':'numeric','metric':'price','operator':'<','threshold':10},'financial_summary')
        with self.assertRaises(Invalid):
            contact_condition({'type':'numeric','metric':'price','operator':'~','threshold':10},'quote_snapshot')
    def test_reminder_and_condition_cannot_be_combined(self):
        from huohuo.contracts import Invalid
        m=self.create();mid=m['mandate']['mandate_id']
        with self.assertRaises(Invalid):
            self.core.command('alice',mid,'revise',{'request_key':'revision-002','expected_revision':1,'expected_generation':0,'goal':m['revision']['goal'],'scope':SCOPE,'contact_note':'到期提醒','reminder_time':'09:00','contact_condition':{'claim':'公告出现重大资产重组'}})
    def test_confirmed_scope_not_reparsed_from_goal(self):
        self.core.create('alice',{'session_id':'test-chat','confirmation_id':self.confirmation,'request_key':'confirmed-001','goal':'原句提到000001，但确认仅研究600519','scope':SCOPE,'contact_note':'在产品中查看'})
        self.core.tick();job=self.repo.claim('worker');self.assertEqual(job['scope'],SCOPE)
    def test_existing_schema_gets_backup_before_new_migration(self):
        import sqlite3
        self.core.store.close()
        with sqlite3.connect(self.repo.path) as db:
            db.execute("DELETE FROM schema_migrations WHERE version='005_execution_handoff'")
        self.core=Mandates(self.repo,'test-instance')
        self.assertTrue(self.repo.path.with_suffix('.sqlite.before-v14').exists())
