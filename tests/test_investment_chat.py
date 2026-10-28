import json
import tempfile
import unittest
from pathlib import Path
from huohuo.execution import Repository, Conflict, Missing
from huohuo.mandates import Mandates
from huohuo.investment.service import Investment
from huohuo.investment.collections import CollectionProvider

class InvestmentChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.core=Mandates(Repository(Path(self.tmp.name)/'db.sqlite'),'test')
        self.inv=Investment(self.core.store)
    def tearDown(self):
        self.core.store.close();self.tmp.cleanup()
    def preview(self,code='513130',cost=None):
        return self.inv.preview('owner',{'command':'holding','payload':{'ticker':code,'name':'合成恒生科技ETF','quantity':1000,'cost_price':cost,'effective_at':'2026-01-01T00:00:00+08:00','reason':'期初快照'}})
    def test_etf_identity_snapshot_event_and_units(self):
        for code in ('513130','513180','159740','510300'):
            p=self.preview(code)
            result=self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']})
            row=next(x for x in result['facts']['holdings'] if x['ticker']==code)
            self.assertEqual(row['quantity_unit'],'份')
            self.assertTrue(row['entity_id'].startswith('FUND:'))
            self.assertIsNone(row['cost_price'])
            self.assertEqual(result['facts']['cost_analysis']['status'],'incomplete')
            self.assertIsNone(result['facts']['cost_analysis']['top_position_cost_weight'])
            members=CollectionProvider(self.inv,'owner').read_snapshot('holdings')['members']
            self.assertIn(row['entity_id'],[m['entity_id'] for m in members])
            event=json.loads(self.core.store._connect().execute('SELECT envelope FROM investment_outbox WHERE event_id=?',(result['event_id'],)).fetchone()[0])
            self.assertIn(row['entity_id'],event['subject_ids'])
        self.assertEqual(self.inv.snapshot('owner',1)['holdings'][0]['quantity_unit'],'份')
    def test_preview_read_ownership_conflict_and_saved_receipt(self):
        p=self.preview('600519',10);pid=p['preview_id']
        self.assertEqual(self.inv.inspect_preview('owner',pid)['command'],'holding')
        with self.assertRaises(Missing):self.inv.inspect_preview('other',pid)
        result=self.inv.commit('owner',{'preview_id':pid,'request_key':pid})
        self.assertEqual(self.inv.inspect_preview('owner',pid)['receipt'],result)
        self.assertEqual(self.inv.read('owner')['version'],1)
        stale=self.preview('600519',20)
        q=self.preview('600519',30);self.inv.commit('owner',{'preview_id':q['preview_id'],'request_key':q['preview_id']})
        with self.assertRaises(Conflict):self.inv.inspect_preview('owner',stale['preview_id'])
    def test_etf_trade_revision_preserves_type_and_unknown_cost(self):
        p=self.preview(cost=1)
        self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']})
        trade=self.inv.preview('owner',{'command':'trade','payload':{'request_id':'etf-trade-1','ticker':'513130','side':'buy','quantity':100,'price':2,'fees':0,'traded_at':'2026-02-01T00:00:00+08:00','affects_holdings':True}})
        self.inv.commit('owner',{'preview_id':trade['preview_id'],'request_key':trade['preview_id']})
        self.assertEqual(self.inv.read('owner')['holdings'][0]['quantity'],1100)
        rev=self.inv.preview('owner',{'command':'revision','payload':{'revision_id':'etf-revision-1','trade_request_id':'etf-trade-1','operation':'void','affects_holdings':True,'reason':'重复录入'}})
        self.inv.commit('owner',{'preview_id':rev['preview_id'],'request_key':rev['preview_id']})
        facts=self.inv.read('owner');self.assertEqual(facts['holdings'][0]['quantity'],1000)
        self.assertEqual(facts['trades'][0]['quantity_unit'],'份')
        self.assertTrue(facts['trades'][0]['voided'])
    def test_noop_commit_has_reconcilable_receipt(self):
        body={'command':'watchlist','payload':{'ticker':'513130','name':'合成ETF','reason':'已移除','remove':True}}
        for _ in range(2):
            p=self.inv.preview('owner',body)
            receipt=self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']})
        self.assertTrue(receipt['duplicate'])
        self.assertEqual(self.inv.inspect_preview('owner',p['preview_id'])['receipt'],receipt)
        self.assertEqual(self.inv.read('owner')['version'],1)
