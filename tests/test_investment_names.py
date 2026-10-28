import json
import tempfile
import unittest
from pathlib import Path
from huohuo.contracts import Invalid
from huohuo.execution import Repository
from huohuo.mandates import Mandates
from huohuo.investment.service import Investment
from huohuo.research_entities import security_search

class InvestmentNamesTests(unittest.TestCase):
    def setUp(self):
        security_search.reset_cache()
        self.tmp=tempfile.TemporaryDirectory()
        self.core=Mandates(Repository(Path(self.tmp.name)/'db.sqlite'),'names')
        self.inv=Investment(self.core.store)
    def tearDown(self):
        self.core.store.close();self.tmp.cleanup();security_search.reset_cache()
    def trade(self, key='names-trade-1', **changes):
        payload={'request_id':key,'ticker':'000001','side':'buy','quantity':200,
                 'price':11.18,'fees':5,'traded_at':'2026-10-26T13:11:00+08:00','affects_holdings':True}
        payload.update(changes)
        return self.inv.preview('owner',{'command':'trade','payload':payload})
    def commit(self, preview):
        return self.inv.commit('owner',{'preview_id':preview['preview_id'],'request_key':preview['preview_id']})
    def dump(self):
        db=self.core.store._connect()
        return {t:[tuple(x) for x in db.execute('select * from '+t)] for t in
                ['investment_facts','investment_versions','investment_audit','investment_outbox']}
    def test_new_trade_name_is_in_server_preview_and_persisted_without_changed_cost(self):
        p=self.trade(name='合成银行')
        self.assertEqual(p['after']['holdings'][0]['name'],'合成银行')
        facts=self.commit(p)['facts']
        self.assertEqual(facts['holdings'][0]['name'],'合成银行')
        self.assertEqual(facts['trades'][0]['name'],'合成银行')
        self.assertEqual(facts['holdings'][0]['cost_price'],11.205)
        self.assertEqual(self.inv.inspect_preview('owner',p['preview_id'])['receipt']['facts'],facts)
    def test_name_survives_other_trade_and_full_sell_and_is_owner_scoped(self):
        self.commit(self.trade(name='合成银行'))
        self.commit(self.trade('other-security',ticker='600519',name='另一合成证券'))
        self.assertEqual(self.inv.read('owner')['holdings'][0]['name'],'合成银行')
        self.commit(self.trade('sell-names-1',side='sell',name='合成银行',fees=0))
        facts=self.inv.read('owner')
        self.assertFalse(any(x['ticker']=='000001' for x in facts['holdings']))
        self.assertTrue(all(x['name']=='合成银行' for x in facts['trades'] if x['ticker']=='000001'))
        self.assertEqual(self.inv.read('other')['trades'],[])
    def test_legacy_name_is_read_only_directory_projection(self):
        self.commit(self.trade())
        before=self.dump()
        security_search.search('000001',loader=lambda:[{'code':'000001','name':'目录银行'}])
        facts=self.inv.read('owner')
        self.assertEqual(facts['holdings'][0]['display_name'],'目录银行')
        self.assertEqual(facts['trades'][0]['display_name'],'目录银行')
        self.assertEqual(facts['cost_analysis']['positions'][0]['name'],'目录银行')
        self.assertNotIn('name',facts['holdings'][0])
        self.assertEqual(facts['holdings'][0]['name_source'],'security_directory')
        self.assertEqual(self.dump(),before)
    def test_code_only_repeat_is_compatible_but_name_change_cannot_reuse_id(self):
        self.commit(self.trade())
        before=self.dump()
        self.assertTrue(self.commit(self.trade())['saved'])
        self.assertEqual(self.inv.read('owner')['version'],1)
        with self.assertRaises(Invalid):self.trade(name='改名')
        self.assertEqual(self.dump(),before)
    def test_recorded_name_wins_over_directory_and_revision_preserves_it(self):
        self.commit(self.trade(name='用户确认名称'))
        security_search.search('000001',loader=lambda:[{'code':'000001','name':'目录银行'}])
        facts=self.inv.read('owner')
        self.assertEqual(facts['holdings'][0]['display_name'],'用户确认名称')
        p=self.inv.preview('owner',{'command':'revision','payload':{'revision_id':'rev-names-1',
            'trade_request_id':'names-trade-1','operation':'amend','quantity':300,'affects_holdings':True}})
        facts=self.commit(p)['facts']
        self.assertEqual(facts['holdings'][0]['name'],'用户确认名称')
        self.assertEqual(facts['trades'][0]['name'],'用户确认名称')
    def test_imported_placeholder_is_not_treated_as_a_recorded_name(self):
        self.commit(self.trade())
        db=self.core.store._connect()
        row=db.execute('select document from investment_facts where principal=?',('owner',)).fetchone()
        doc=json.loads(row[0]);doc['default'][0]['name']='证券名称待补全'
        db.execute('update investment_facts set document=? where principal=?',(json.dumps(doc),'owner'))
        before=self.dump()
        security_search.search('000001',loader=lambda:[{'code':'000001','name':'目录银行'}])
        facts=self.inv.read('owner')
        self.assertEqual(facts['holdings'][0]['display_name'],'目录银行')
        self.assertEqual(facts['holdings'][0]['name'],'证券名称待补全')
        self.assertEqual(self.dump(),before)
