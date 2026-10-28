import json
import tempfile
import unittest
from huohuo.contracts import Invalid
from huohuo.execution import Conflict,Missing,digest
from huohuo.investment.service import Investment
from huohuo.transfer import TransferService
from test_transfer_fixtures import Fixture,snapshot,package,mandate_entry


class TransferServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(self.tmp.name);self.addCleanup(self.f.store.close)

    def test_snapshot_versions_preview_without_business_writes(self):
        for version in (1,2,3,4):
            upload=self.f.upload(snapshot(version));preview=self.f.preview(upload)
            self.assertTrue(preview['can_commit'])
            self.assertEqual(Investment(self.f.store).read('owner')['version'],0)
        self.assertEqual(self.f.store._connect().execute('SELECT count(*) FROM strategy_documents').fetchone()[0],0)

    def test_full_import_is_atomic_persisted_and_truthful(self):
        preview=self.f.preview(self.f.upload(package(mandates=[mandate_entry()])))
        self.assertTrue(preview['can_commit'])
        receipt=self.f.commit(preview)
        self.assertEqual(receipt['status'],'committed')
        facts=Investment(self.f.store).read('owner')
        self.assertEqual(facts['version'],1)
        self.assertEqual(facts['holdings'][0]['quantity'],10)
        self.assertEqual(facts['holdings'][0]['name'],'贵州茅台')
        self.assertFalse(facts['trades'][0]['affects_holdings'])
        self.assertIsNone(facts['trades'][0]['fees'])
        self.assertEqual(facts['watchlist'][0]['name'],'平安银行')
        db=self.f.store._connect()
        strategy=json.loads(db.execute("SELECT document FROM strategy_documents WHERE collection='strategies'").fetchone()[0])
        self.assertEqual(strategy['status'],'candidate');self.assertEqual(strategy['backtest'],{})
        mandate=db.execute('SELECT * FROM mandates').fetchone()
        self.assertEqual((mandate['principal_id'],mandate['instance_id'],mandate['status']),('owner','new-instance','paused'))
        self.assertIsNone(mandate['source_session_id'])
        self.assertEqual(db.execute('SELECT enabled FROM mandate_schedules').fetchone()[0],0)
        policy=json.loads(db.execute('SELECT contact_policy_json FROM mandate_revisions').fetchone()[0])
        self.assertEqual(policy['channels'],[])
        self.assertEqual(db.execute('SELECT count(*) FROM research_jobs').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT count(*) FROM investment_versions').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT count(*) FROM investment_audit').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT count(*) FROM legacy_transfer_audit').fetchone()[0],1)
        archive=self.f.service.archive('owner')
        self.assertGreater(archive['total'],3)
        report=next(x for x in archive['items'] if x['title']=='旧合成报告')
        detail=self.f.service.archive('owner',archive_id=report['id'])
        self.assertNotIn('api_key',detail['document'])
        self.assertFalse(detail['source']['new_research_evidence'])
        self.assertFalse(detail['source']['dsh_session'])

    def test_cancel_cross_user_and_session_checks(self):
        preview=self.f.preview(self.f.upload())
        with self.assertRaises(Missing): self.f.commit(preview,'someone-else')
        with self.assertRaises(Missing): self.f.commit(preview,session='other-chat')
        self.f.service.cancel('owner','chat',preview['preview_id'])
        with self.assertRaises(Conflict): self.f.commit(preview)
        self.assertEqual(Investment(self.f.store).read('owner')['version'],0)

    def test_commit_receipt_survives_response_loss_and_restart(self):
        preview=self.f.preview(self.f.upload())
        receipt=self.f.commit(preview)
        restarted=TransferService(self.f.store,'new-instance',clock=lambda:self.f.clock)
        state=restarted.status('owner','chat',preview['preview_id'])
        self.assertEqual(state['receipt'],receipt)
        self.assertEqual(self.f.commit(preview),receipt)
        self.assertEqual(Investment(self.f.store).read('owner')['version'],1)
        with self.assertRaises(Conflict): self.f.service.cancel('owner','chat',preview['preview_id'])

    def test_version_conflict_blocks_entire_plan(self):
        preview=self.f.preview(self.f.upload())
        inv=Investment(self.f.store)
        operation=inv.preview('owner',{'command':'watchlist','payload':{'ticker':'600519','name':'贵州茅台','reason':'新操作','remove':False}})
        inv.commit('owner',{'preview_id':operation['preview_id'],'request_key':'other-business'})
        with self.assertRaises(Conflict): self.f.commit(preview)
        self.assertEqual(self.f.store._connect().execute('SELECT count(*) FROM legacy_transfer_audit').fetchone()[0],0)
        state=self.f.service.status('owner','chat',preview['preview_id'])
        self.assertEqual(state['status'],'stale')
        self.assertFalse(state['can_commit'])
        self.f.service.cancel('owner','chat',preview['preview_id'])
        renewed=self.f.preview(self.f.service.uploads('owner')['items'][0])
        self.assertTrue(renewed['can_commit'])

    def test_one_bad_selected_record_blocks_other_valid_categories(self):
        value=snapshot();value['categories']['holdings']['collections']['holdings']['default'][0]['quantity']=-10
        value['revision']=digest({key:item['collections'] for key,item in value['categories'].items()})
        upload=self.f.upload(value);preview=self.f.preview(upload)
        self.assertFalse(preview['can_commit']);self.assertTrue(preview['blockers'])
        with self.assertRaises(Invalid): self.f.commit(preview)
        self.assertEqual(Investment(self.f.store).read('owner')['version'],0)
        valid=self.f.preview(upload,['watchlist'])
        self.assertTrue(valid['can_commit']);self.f.commit(valid)
        self.assertEqual(len(Investment(self.f.store).read('owner')['watchlist']),1)

    def test_failure_rolls_back_facts_strategies_mandates_archives(self):
        preview=self.f.preview(self.f.upload(package(mandates=[mandate_entry()])))
        db=self.f.store._connect()
        db.execute("CREATE TRIGGER deny_archive BEFORE INSERT ON legacy_transfer_archives BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(Exception): self.f.commit(preview)
        for table in ('investment_facts','investment_versions','investment_audit','strategy_documents','mandates','legacy_transfer_archives','legacy_transfer_audit'):
            self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0,table)
        self.assertEqual(self.f.service.status('owner','chat',preview['preview_id'])['status'],'pending')

    def test_idempotent_second_upload_does_not_duplicate_facts_or_archives(self):
        self.f.commit(self.f.preview(self.f.upload()))
        before=self.f.service.archive('owner')['total']
        self.f.clock+=60
        receipt=self.f.commit(self.f.preview(self.f.upload()))
        self.assertFalse(receipt['result']['facts']['changed'])
        self.assertEqual(receipt['result']['strategies'],0)
        self.assertEqual(receipt['result']['archives_added'],0)
        self.assertEqual(self.f.service.archive('owner')['total'],before)

    def test_expiry_and_request_reuse(self):
        upload=self.f.upload();preview=self.f.preview(upload)
        self.f.clock+=1801
        with self.assertRaises(Conflict): self.f.commit(preview)
        with self.assertRaises(Conflict): self.f.service.prepare('owner','chat',{'request_key':preview['request_key'],'upload_id':upload['upload_id'],'selected':['research'],'rules':{}})
        self.f.service.remove_upload('owner','chat',upload['upload_id'])
        with self.assertRaises(Conflict): self.f.commit(preview)

    def test_integrity_paths_duplicate_fields_and_future_format_rejected(self):
        value=package();value['domains']['trading-core']['payload']['schemaVersion']=3
        with self.assertRaises(Invalid): self.f.upload(value)
        value=snapshot();value['schemaVersion']=5
        with self.assertRaises(Invalid): self.f.upload(value)
        for filename,content in (('../old.json','{}'),('old.json','{"backend":"trading-core","backend":"x"}'),('old.json','{"x":NaN}')):
            with self.assertRaises(Invalid): self.f.service.upload('owner','chat',{'request_key':'invalid','filename':filename,'content':content})

    def test_history_archive_and_preview_cannot_cross_owner(self):
        receipt=self.f.commit(self.f.preview(self.f.upload()))
        items=self.f.service.archive('owner')['items']
        self.assertEqual(self.f.service.archive('other')['total'],0)
        with self.assertRaises(Missing): self.f.service.archive('other',archive_id=items[0]['id'])
