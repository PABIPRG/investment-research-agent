import copy
import json
import tempfile
import unittest
from huohuo.contracts import Invalid
from huohuo.execution import Conflict, Missing, digest
from huohuo.investment.service import Investment
from test_transfer_fixtures import Fixture, snapshot, package, mandate_entry


def revision(value):
    value['revision']=digest({key:item['collections'] for key,item in value['categories'].items()})
    return value


class TransferEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(self.tmp.name);self.addCleanup(self.f.store.close)

    def test_same_owner_upload_is_selectable_but_preview_is_session_bound(self):
        upload=self.f.upload();self.assertEqual(len(self.f.service.uploads('owner')['items']),1)
        self.assertEqual(self.f.service.uploads('other')['items'],[])
        body={'upload_id':upload['upload_id'],'request_key':'chat-import','selected':['watchlist'],'rules':{}}
        with self.assertRaises(Missing): self.f.service.prepare('other','other-chat',body)
        p=self.f.service.prepare('owner','other-chat',body)
        with self.assertRaises(Missing): self.f.service.status('owner','chat',p['preview_id'])
        self.f.service.commit('owner','other-chat',{'preview_id':p['preview_id'],'request_key':p['request_key']})

    def test_expired_preview_is_not_displayed_as_committable(self):
        p=self.f.preview(self.f.upload());self.f.clock+=1801
        state=self.f.service.status('owner','chat',p['preview_id'])
        self.assertEqual(state['status'],'expired');self.assertFalse(state['can_commit'])

    def test_preview_describes_concrete_holdings_and_unknown_fees(self):
        p=self.f.preview(self.f.upload())
        changes=self.f.service.preview_changes('owner','chat',p['preview_id'],limit=1)
        self.assertEqual(changes['items'][0]['after'],{'quantity':10.,'cost_price':100.})
        self.assertGreater(changes['total'],1)
        detail=self.f.service.preview_changes('owner','chat',p['preview_id'],category='holdings')
        trade=next(x for x in detail['items'] if x['kind']=='补记历史成交')
        self.assertIsNone(trade['after']['fees']);self.assertFalse(trade['after']['affects_holdings'])
        with self.assertRaises(Missing):self.f.service.preview_changes('other','chat',p['preview_id'])

    def test_holdings_conflict_keep_local_and_use_import(self):
        inv=Investment(self.f.store)
        p=inv.preview('owner',{'command':'holding','payload':{'ticker':'600519','name':'贵州茅台','quantity':20,'cost_price':None,'effective_at':'2025-01-01T09:30:00+08:00','reason':'当前快照'}})
        inv.commit('owner',{'preview_id':p['preview_id'],'request_key':'new-snapshot'})
        upload=self.f.upload();keep=self.f.preview(upload,['holdings'])
        self.assertEqual(keep['summary']['holdings']['conflicts'],1)
        self.f.commit(keep);self.assertEqual(inv.read('owner')['holdings'][0]['quantity'],20)
        imported=self.f.preview(upload,['holdings'],{'holdings':'use_import'})
        detail=next(x for x in imported['changes']['items'] if x['kind']=='更新')
        self.assertEqual(detail['before'],{'cost_price':None,'quantity':20})
        self.f.commit(imported);self.assertEqual(inv.read('owner')['holdings'][0]['quantity'],10)

    def test_simulation_and_unclassified_are_archive_only(self):
        value=snapshot();entries=value['categories']['holdings']['collections']['trades']['entries']
        entries += [{**entries[0],'trade_id':'simulation','account_mode':'simulated'}, {**entries[0],'trade_id':'gift','side':'unclassified','price':0}]
        p=self.f.preview(self.f.upload(revision(value)));self.f.commit(p)
        self.assertEqual(p['summary']['holdings']['archive_only_trades'],2)
        facts=Investment(self.f.store).read('owner')
        self.assertEqual(len(facts['trades']),1);self.assertEqual(facts['holdings'][0]['quantity'],10)
        self.assertEqual(facts['trades'][0]['traded_at'],'2025-01-01T09:30+08:00')

    def test_bad_mandate_reference_and_duplicates_block_in_preview(self):
        for mode in ('revision','duplicate'):
            m=mandate_entry()
            if mode=='revision':m['revisions'][0]['revision']['mandate_id']='MND_'+'2'*32
            else:m['schedules']*=2
            p=self.f.preview(self.f.upload(package(mandates=[m])))
            self.assertFalse(p['can_commit']);self.assertEqual(p['blockers'][0]['category'],'mandates')

    def test_unknown_strategy_blocks_selected_batch(self):
        value=snapshot();value['categories']['strategies']['collections']['strategies']['old-strategy']['kind']='unmapped-python-strategy'
        p=self.f.preview(self.f.upload(revision(value)))
        self.assertFalse(p['can_commit']);self.assertEqual(p['blockers'][0]['category'],'strategies')

    def test_credentials_excluded_before_candidate_is_persisted(self):
        self.f.upload();stored=self.f.store._connect().execute('SELECT payload FROM legacy_transfer_uploads').fetchone()[0]
        self.assertNotIn('synthetic-only-not-a-credential',stored);self.assertNotIn('api_key',stored)

    def test_failed_commit_can_be_explicitly_retried_after_rollback(self):
        p=self.f.preview(self.f.upload());db=self.f.store._connect()
        db.execute("CREATE TRIGGER deny_import BEFORE INSERT ON legacy_transfer_audit BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(Exception):self.f.commit(p)
        self.assertIsNone(self.f.service.status('owner','chat',p['preview_id'])['receipt'])
        db.execute('DROP TRIGGER deny_import');self.assertEqual(self.f.commit(p)['status'],'committed')

    def test_imported_trade_revision_cannot_recalculate_or_invent_fees(self):
        self.f.commit(self.f.preview(self.f.upload()))
        inv=Investment(self.f.store);facts=inv.read('owner');trade=facts['trades'][0]
        payload={'trade_request_id':trade['request_id'],'revision_id':'old-amend-001','operation':'amend','price':110}
        with self.assertRaises(Invalid):inv.preview('owner',{'command':'revision','payload':payload})
        payload['affects_holdings']=False
        p=inv.preview('owner',{'command':'revision','payload':payload})
        result=inv.commit('owner',{'preview_id':p['preview_id'],'request_key':'amend-1'})
        self.assertIsNone(result['facts']['trades'][0]['fees'])
        self.assertFalse(result['facts']['trades'][0]['fees_known'])
        self.assertEqual(result['facts']['holdings'],facts['holdings'])
        payload.update({'revision_id':'old-amend-002','fees':0})
        p=inv.preview('owner',{'command':'revision','payload':payload})
        result=inv.commit('owner',{'preview_id':p['preview_id'],'request_key':'amend-2'})
        self.assertTrue(result['facts']['trades'][0]['fees_known'])
        payload={'trade_request_id':trade['request_id'],'revision_id':'old-void-001','operation':'void','affects_holdings':False}
        p=inv.preview('owner',{'command':'revision','payload':payload})
        result=inv.commit('owner',{'preview_id':p['preview_id'],'request_key':'void-1'})
        self.assertEqual(result['facts']['holdings'],facts['holdings']);self.assertTrue(result['facts']['trades'][0]['voided'])

    def test_record_only_revision_keeps_unknown_current_cost_in_preview(self):
        value=snapshot();value['categories']['holdings']['collections']['holdings']['default'][0]['cost_price']=None
        self.f.commit(self.f.preview(self.f.upload(revision(value))))
        inv=Investment(self.f.store);trade=inv.read('owner')['trades'][0]
        p=inv.preview('owner',{'command':'revision','payload':{'trade_request_id':trade['request_id'],'revision_id':'unknown-cost-revise','operation':'amend','price':105,'affects_holdings':False}})
        self.assertIsNone(p['after']['holdings'][0]['cost_price'])
        self.assertIsNone(p['impact']['impact']['current']['cost_price'])
        self.assertIsNone(p['impact']['impact']['projected']['cost_price'])
