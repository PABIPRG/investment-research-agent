import tempfile, unittest
from pathlib import Path
from huohuo.execution import Repository, Conflict
from huohuo.mandates import Mandates
from huohuo.investment.service import Investment

class InvestmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.repo=Repository(Path(self.tmp.name)/'db.sqlite');self.core=Mandates(self.repo,'test');self.inv=Investment(self.core.store)
    def tearDown(self): self.core.store.close();self.tmp.cleanup()
    def save(self,command,payload):
        p=self.inv.preview('owner',{'command':command,'payload':payload})
        return self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']})
    def trade(self,key,qty=10,affects=True):return self.save('trade',{'request_id':key,'ticker':'600519','side':'buy','quantity':qty,'price':10,'fees':0,'traded_at':'2025-01-02T10:00:00+08:00','affects_holdings':affects})
    def test_record_only_never_replayed(self):
        self.trade('trade-one');self.trade('trade-two',100,False)
        self.save('revision',{'revision_id':'revision-one','trade_request_id':'trade-one','operation':'amend','quantity':20,'affects_holdings':True})
        self.assertEqual(self.inv.read('owner')['holdings'][0]['quantity'],20)
    def test_conflict_and_idempotency(self):
        p=self.inv.preview('owner',{'command':'watchlist','payload':{'ticker':'600519','name':'贵州茅台','reason':'长期研究','remove':False}})
        self.trade('trade-one')
        with self.assertRaises(Conflict):self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':'conflict'})
        p=self.inv.preview('owner',{'command':'watchlist','payload':{'ticker':'600519','name':'贵州茅台','reason':'长期研究','remove':False}})
        body={'preview_id':p['preview_id'],'request_key':'repeat'}
        self.assertEqual(self.inv.commit('owner',body),self.inv.commit('owner',body))
        self.assertEqual(self.inv.read('owner')['version'],2)
    def test_rollback(self):
        p=self.inv.preview('owner',{'command':'trade','payload':{'request_id':'trade-one','ticker':'600519','side':'buy','quantity':10,'price':10,'traded_at':'2025-01-02T10:00:00Z','affects_holdings':True}})
        self.core.store._connect().execute("CREATE TRIGGER fail_event BEFORE INSERT ON investment_outbox BEGIN SELECT RAISE(ABORT,'fail'); END")
        with self.assertRaises(Exception):self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':'rollback'})
        self.assertEqual(self.inv.read('owner')['version'],0)
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM investment_audit').fetchone()[0],0)
    def test_owner_isolation(self):
        self.trade('trade-one');self.assertEqual(self.inv.read('other')['status'],'not_recorded')
        with self.assertRaises(Exception):self.inv.snapshot('other',1)
    def mandate(self,owner='owner'):
        from huohuo.research_partner.commands import MandateCreateRequest
        view=self.core.service.create(self.core.context(owner),MandateCreateRequest(goal='明确研究茅台报价',scope={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'},subjects=[{'entity_id':'SEC:CN:A:600519'}],idempotency_key='create-mandate'))
        mid=view['mandate']['mandate_id'];self.core.store._connect().execute('INSERT INTO mandate_generation VALUES(?,0)',(mid,));return mid
    def bind(self,mid,mode='fixed'):
        view=self.core.get('owner',mid)
        return self.core.investment_binding.bind('owner',{'mandate_id':mid,'collection':'holdings','mode':mode,'expected_revision':view['mandate']['current_revision'],'expected_generation':view['generation'],'expected_fact_version':self.inv.read('owner')['version'],'request_key':'binding-'+mode})
    def test_fixed_dynamic_and_execution_snapshot(self):
        self.trade('trade-one');mid=self.mandate();self.bind(mid)
        self.trade('trade-two',20)
        with self.core.store.transaction():self.core.investment_binding.capture('owner',mid,'fixed-run')
        row=self.core.store._connect().execute('SELECT version FROM investment_run_facts WHERE execution_id=?',('fixed-run',)).fetchone();self.assertEqual(row[0],1)
        self.bind(mid,'dynamic')
        with self.core.store.transaction():self.core.investment_binding.capture('owner',mid,'dynamic-run')
        row=self.core.store._connect().execute('SELECT version FROM investment_run_facts WHERE execution_id=?',('dynamic-run',)).fetchone();self.assertEqual(row[0],2)
        self.assertEqual(self.inv.snapshot('owner',1)['holdings'][0]['quantity'],10)
    def test_events_replay_and_paused_no_restart(self):
        self.trade('trade-one');mid=self.mandate();self.bind(mid,'dynamic');self.core.tick()
        db=self.core.store._connect();count=db.execute('SELECT count(*) FROM research_jobs').fetchone()[0]
        db.execute('UPDATE investment_outbox SET published=0');self.core.tick()
        self.assertEqual(db.execute('SELECT count(*) FROM research_jobs').fetchone()[0],count)
        view=self.core.get('owner',mid);self.core.command('owner',mid,'pause',{'request_key':'pause-test','expected_revision':view['mandate']['current_revision'],'expected_generation':view['generation']})
        self.trade('trade-two');self.core.tick()
        self.assertEqual(self.core.get('owner',mid)['mandate']['status'],'paused')
        self.assertEqual(db.execute('SELECT count(*) FROM research_jobs').fetchone()[0],count)
    def test_unknown_cost_correction_and_gap(self):
        self.save('holding',{'ticker':'600519','name':'贵州茅台','quantity':10,'cost_price':None,'effective_at':'2025-02-01T10:00:00Z','reason':'期初持仓，成本未知'})
        self.assertIsNone(self.inv.read('owner')['holdings'][0]['cost_price'])
        self.trade('history-record',10,False)
        self.assertIsNone(self.inv.read('owner')['holdings'][0]['cost_price'])
    def test_events_only_matching_owner_and_collection(self):
        self.trade('trade-one');mid=self.mandate();self.bind(mid,'dynamic');other=self.mandate('other');self.core.tick()
        db=self.core.store._connect();before=db.execute('SELECT count(*) FROM research_jobs WHERE mandate_id=?',(mid,)).fetchone()[0]
        self.save('watchlist',{'ticker':'600519','name':'贵州茅台','reason':'无关集合','remove':False});self.core.tick()
        self.assertEqual(db.execute('SELECT count(*) FROM research_jobs WHERE mandate_id=?',(mid,)).fetchone()[0],before)
        self.trade('trade-two');self.core.tick()
        self.assertEqual(db.execute('SELECT count(*) FROM research_jobs WHERE mandate_id=?',(mid,)).fetchone()[0],before+1)
        self.assertEqual(db.execute('SELECT count(*) FROM research_jobs WHERE mandate_id=?',(other,)).fetchone()[0],1)
    def test_record_only_amend_does_not_leak_into_future_replay(self):
        self.trade('trade-one')
        self.save('revision',{'revision_id':'revision-only','trade_request_id':'trade-one','operation':'amend','quantity':100,'affects_holdings':False})
        self.trade('trade-two')
        self.save('revision',{'revision_id':'revision-next','trade_request_id':'trade-two','operation':'amend','quantity':20,'affects_holdings':True})
        self.assertEqual(self.inv.read('owner')['holdings'][0]['quantity'],30)
    def test_future_time_and_oversell_rejected(self):
        from huohuo.contracts import Invalid
        self.trade('trade-one')
        with self.assertRaises(Invalid):self.save('trade',{'request_id':'oversell-key','ticker':'600519','side':'sell','quantity':11,'price':10,'traded_at':'2025-01-02T10:00:00Z','affects_holdings':True})
        with self.assertRaises(Invalid):self.save('trade',{'request_id':'future-key','ticker':'600519','side':'buy','quantity':11,'price':10,'traded_at':'2099-01-02T10:00:00Z','affects_holdings':True})
        self.assertEqual(self.inv.read('owner')['version'],1)
    def test_watchlist_does_not_confirm_empty_holdings(self):
        from huohuo.investment.collections import CollectionProvider
        self.save('watchlist',{'ticker':'600519','name':'贵州茅台','reason':'只关注','remove':False})
        self.assertEqual(CollectionProvider(self.inv,'owner').read_snapshot('holdings')['status'],'not_recorded')
        self.assertEqual(CollectionProvider(self.inv,'owner').read_snapshot('watchlist')['status'],'ready')
    def test_collection_port_and_upgrade_backup(self):
        from huohuo.investment.collections import CollectionProvider
        from huohuo.research_partner.adapters import SqliteBusinessStore
        import sqlite3
        self.assertIsNone(CollectionProvider(self.inv,'owner').get_collection('holdings'))
        self.trade('trade-one')
        collection=CollectionProvider(self.inv,'owner').get_collection('holdings')
        self.assertEqual(collection.member_entity_ids,['SEC:CN:A:600519'])
        self.assertEqual(collection.filter_definition['fact_version'],1)
        # 在独立空库上模拟共享快照的 007 schema，再重新加载本迁移。
        path=Path(self.tmp.name)/'upgrade.sqlite';store=SqliteBusinessStore(path);db=store._connect()
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'investment_%'").fetchall():db.execute('DROP TABLE '+row['name'])
        db.execute("DELETE FROM schema_migrations WHERE version='008_investment'");store.close()
        upgraded=SqliteBusinessStore(path)
        self.assertTrue(path.with_suffix('.sqlite.before-investment').exists())
        self.assertEqual(upgraded._connect().execute("SELECT count(*) FROM investment_facts").fetchone()[0],0)
        upgraded.close()
    def test_revision_crosses_opening_snapshot_reports_gap(self):
        self.save('holding',{'ticker':'600519','name':'贵州茅台','quantity':100,'cost_price':10,'effective_at':'2025-02-01T10:00:00Z','reason':'期初持仓'})
        self.save('trade',{'request_id':'later-buy','ticker':'600519','side':'buy','quantity':10,'price':10,'traded_at':'2025-03-01T10:00:00Z','affects_holdings':True})
        p=self.inv.preview('owner',{'command':'revision','payload':{'revision_id':'revision-early','trade_request_id':'later-buy','operation':'amend','traded_at':'2025-01-01T10:00:00Z','affects_holdings':True}})
        self.assertIn('trades_before_opening_snapshot',[x['code'] for x in p['impact']['gaps']])
