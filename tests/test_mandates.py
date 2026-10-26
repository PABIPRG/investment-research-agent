import tempfile
import unittest
from pathlib import Path
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates

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
        ev=self.repo.save_evidence(job['attempt_id'],job['lease_token'],{'scope':SCOPE,'status':'ok','source':'fixture','observed_at':'2026-10-23T00:00:00Z','values':{'price':'10'}})
        result={'status':'succeeded','execution_id':job['execution_id'],'scope':SCOPE,'summary':'测试来源的报价','evidence_ids':[ev['evidence_id']]}
        self.repo.finish(job['attempt_id'],job['lease_token'],result)
        return result
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
