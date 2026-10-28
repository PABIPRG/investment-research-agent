"""策略全链路受控回归；行情均为显式注入的合成样本，不是市场收益。"""
import math
import tempfile
import unittest
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from huohuo.execution import Repository, Conflict, Missing
from huohuo.mandates import Mandates
from huohuo.contracts import Invalid
from huohuo.strategies.service import Strategies


def bars(start='2025-01-01', count=260):
    start = date.fromisoformat(start)
    result = []
    for i in range(count):
        price = 20 + i * .015 + 4 * math.sin(i / 7)
        result.append({'date': (start + timedelta(days=i)).isoformat(),
                       'open': price, 'high': price+1, 'low': price-1,
                       'close': price+.2, 'volume': 100000+i})
    return result


class StrategyDomainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.time = datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp()
        self.repo = Repository(Path(self.tmp.name)/'test.sqlite', clock=lambda:self.time)
        self.core = Mandates(self.repo, 'strategy-tests')
        self.calls = []
        def history(code, start, end):
            self.calls.append((code,start,end))
            return {'records':[x for x in bars(count=800) if start<=x['date']<=end],
                    'source':'synthetic:strategy-domain-tests', 'adjustment':'qfq'}
        self.service = Strategies(self.core.store, history=history, clock=lambda:self.time)
        self.seq = 0
    def tearDown(self):
        self.core.store.close(); self.tmp.cleanup()
    def prepare(self, action, payload, owner='alice', session='chat'):
        self.seq += 1
        return self.service.prepare(owner,session,{'request_key':f'k{self.seq}', 'action':action,'payload':payload})
    def command(self, action, payload, owner='alice'):
        p = self.prepare(action,payload,owner)
        return self.service.commit(owner,'chat',{'preview_id':p['preview_id'],'request_key':p['request_key']})
    def create(self):
        return self.command('create',{'name':'合成动量验证', 'kind':'momentum','params':{'n':5},
            'securities':[{'code':'600519','name':'贵州茅台'}],
            'rationale':'用于受控测试的合成假设，不代表投资建议', 'direction':'利好'})['strategy']
    def test_new_instance_unknown_returns_and_no_network(self):
        with patch('requests.Session.get',side_effect=AssertionError('no HTTP')):
            view=self.service.read('alice')
        self.assertEqual(view['strategies'],[])
        self.assertIsNone(view['attribution']['overall'])
        self.assertFalse(view['pool']['closed_loop_enabled'])
        self.assertEqual(view['preview']['preview_status'],'none')
        self.assertEqual(self.calls,[])
    def test_confirmation_is_scoped_idempotent_and_versioned(self):
        p=self.prepare('create',{'name':'测试规则','kind':'momentum','params':{'n':10},
            'securities':[{'code':'600519','name':'贵州茅台'}],'direction':'利好','rationale':'测试假设'})
        self.assertEqual(self.service.read('alice')['strategies'],[])
        for user,session in [('bob','chat'),('alice','other')]:
            with self.assertRaises(Missing):self.service.commit(user,session,{'preview_id':p['preview_id'],'request_key':p['request_key']})
        body={'preview_id':p['preview_id'],'request_key':p['request_key']}
        one=self.service.commit('alice','chat',body)
        self.assertEqual(one,self.service.commit('alice','chat',body))
        self.assertEqual(one['strategy']['status'],'candidate')
        self.assertEqual(self.service.read('bob')['strategies'],[])
        with self.assertRaises(Conflict):self.service.commit('alice','chat',{**body,'request_key':'forged'})
    def test_full_chain_persists_real_computations(self):
        s=self.create();sid=s['id']
        result=self.command('backtest',{'strategy_id':sid,'revision':s['revision'],
            'start_date':'2025-01-01','end_date':'2025-09-30'})
        s=result['strategy'];self.assertEqual(s['status'],'active')
        self.assertIn(s['verification_status'],('passed','not_passed','insufficient'))
        self.assertEqual(result['run']['status'],'completed')
        self.assertIn('out_of_sample',s['backtest'])
        self.assertTrue(s['backtest']['extended_backtest']['equity_curve']['out']['date'])
        self.assertTrue(result['run']['evidence'])
        for _ in range(6):
            self.command('shadow',{'strategy_id':sid,'revision':s['revision']})
            self.time+=86400
            s=self.service.read('alice',sid)['strategies'][0]
        view=self.service.read('alice',sid)
        self.assertEqual(view['attribution']['days_of_data'],6)
        self.assertIsNotNone(view['attribution']['overall'])
        generated=self.command('evolve',{'strategy_id':sid,'revision':s['revision']})
        self.assertIn('actions',generated['evolution'])
        self.assertFalse(generated['evolution']['applied'])
        self.assertEqual(self.service.read('alice',sid)['preview']['preview_status'],'pending' if generated['evolution']['actions'] else 'none')
        restarted=Strategies(self.core.store,history=self.service.history,clock=lambda:self.time)
        self.assertEqual(restarted.read('alice',sid)['attribution'],view['attribution']|{'as_of':restarted.read('alice',sid)['attribution']['as_of']})
    def test_failures_do_not_activate_or_fabricate_shadow(self):
        s=self.create()
        self.service.history=lambda *_:(_ for _ in ()).throw(RuntimeError('synthetic source failed'))
        p=self.prepare('backtest',{'strategy_id':s['id'],'revision':s['revision'],
            'start_date':'2025-01-01','end_date':'2025-09-30'})
        r=self.service.commit('alice','chat',{'preview_id':p['preview_id'],'request_key':p['request_key']})
        self.assertEqual(r['run']['status'],'failed')
        self.assertEqual(r['strategy']['status'],'candidate')
        self.assertIsNone(self.service.read('alice')['attribution']['overall'])
    def test_invalid_rules_dates_and_symbols_rejected(self):
        base={'name':'测试','kind':'ma_cross','params':{'fast':20,'slow':5},
              'securities':[{'code':'600519','name':'贵州茅台'}],'direction':'利好','rationale':'测试'}
        for bad in [base,base|{'kind':'arbitrary'},base|{'params':{'fast':5,'slow':20,'shell':'bad'}},
                    base|{'kind':'momentum','params':{'n':float('nan')}},
                    base|{'securities':[{'code':'../data','name':'bad'}]}]:
            with self.assertRaises(Invalid):self.prepare('create',bad)
        s=self.create()
        for start,end in [('2025-02-30','2025-09-30'),('2024-01-01','2028-01-01')]:
            with self.assertRaises(Invalid):self.prepare('backtest',{'strategy_id':s['id'],'revision':s['revision'],'start_date':start,'end_date':end})
    def test_read_does_not_mutate_and_unknown_scope_never_falls_back(self):
        s=self.create(); db=self.core.store._connect()
        before=db.total_changes
        self.service.read('alice'); self.service.read('alice')
        self.assertEqual(before,db.total_changes)
        for sid in ['missing','../data']:
            with self.assertRaises((Invalid,Missing)):self.service.read('alice',sid)
    def test_expired_preview_cannot_write(self):
        s=self.create();p=self.prepare('retire',{'strategy_id':s['id'],'revision':s['revision']})
        self.time+=1900
        with self.assertRaises(Conflict):self.service.commit('alice','chat',{'preview_id':p['preview_id'],'request_key':p['request_key']})
        self.assertEqual(self.service.read('alice')['strategies'][0]['status'],'candidate')

if __name__=='__main__':unittest.main()
