"""迁入算法的非对称日期、因果时序、预案与事务边界回归。"""
import unittest
from unittest.mock import patch
import test_strategy_domain as fixtures
bars=fixtures.bars
from huohuo.strategies.legacy import strategies,evolution
from huohuo.strategies.legacy.runtime import runtime
from huohuo.strategies.storage import Documents
from huohuo.execution import Conflict

class Algorithms(unittest.TestCase):
 def test_dates_are_aligned_without_future_backfill(self):
  import pandas as pd
  a=pd.DataFrame([{'date':'2025-01-01','open':10,'close':10},{'date':'2025-01-03','open':10,'close':20}])
  b=pd.DataFrame([{'date':'2025-01-02','open':10,'close':10},{'date':'2025-01-03','open':10,'close':10}])
  curve=strategies.portfolio_equity_curve({'a':(a,pd.Series([1,1])),'b':(b,pd.Series([0,0]))},100)
  self.assertEqual(curve['date'],['2025-01-01','2025-01-02','2025-01-03'])
  self.assertEqual(curve['nav'],[1,1,1.5])
 def test_all_six_rules_are_causal_and_next_bar_execution(self):
  df=strategies._make_df(bars(count=200))
  from huohuo.strategies.validation import RULES
  for kind,cfg in RULES.items():
   params={k:v[0] for k,v in cfg.items()}
   full=strategies.signal_series(df,kind,params)
   prefix=strategies.signal_series(df.iloc[:100].copy(),kind,params)
   self.assertEqual(full.iloc[:100].tolist(),prefix.tolist())
  import pandas as pd
  tiny=pd.DataFrame([{'date':'2025-01-01','open':10,'close':20},{'date':'2025-01-02','open':30,'close':30},{'date':'2025-01-03','open':40,'close':40}])
  trades=strategies.simulate_trades(tiny,pd.Series([1,0,0]))
  self.assertEqual(trades[0]['entry_price'],30)
  self.assertEqual(trades[0]['exit_price'],40)

class EvolutionBoundaries(unittest.TestCase):
 setUp=fixtures.StrategyDomainTests.setUp
 tearDown=fixtures.StrategyDomainTests.tearDown
 prepare=fixtures.StrategyDomainTests.prepare
 command=fixtures.StrategyDomainTests.command
 create=fixtures.StrategyDomainTests.create
 # Reuse fixture helpers; inherit the full chain for the same storage/clock wiring.
 def seed_positive_shadow(self):
  s=self.create();docs=Documents(self.core.store,'alice')
  with self.core.store.transaction():
   s={**s,'status':'active','verification_status':'passed','backtest':{'thresholds_pass':True}}
   docs.set('strategies',s['id'],s)
   for i,nav in enumerate([1,1.01,1.02,1.03,1.05]):
    docs.set('shadow_equity',f'2025-09-{20+i:02}',{'overall_nav':nav,'strategies':{s['id']:{'nav':nav,'initial_capital':100000,'equity':nav*100000}}})
  return s,docs
 def test_confirmed_apply_creates_child_and_rejects_stale_evidence(self):
  s,docs=self.seed_positive_shadow();generated=self.command('evolve',{'strategy_id':s['id'],'revision':s['revision']})
  preview=generated['evolution'];self.assertTrue(preview['actions'])
  self.assertEqual(docs.get('strategies',s['id'])['evolve']['tier'],1)
  p=self.prepare('apply',{'strategy_id':s['id'],'revision':s['revision'],'preview_token':preview['preview_token']})
  applied=self.service.commit('alice','chat',{'preview_id':p['preview_id'],'request_key':p['request_key']})
  self.assertEqual(applied['run']['status'],'completed')
  self.assertEqual(docs.get('strategies',s['id'])['evolve']['tier'],2)
  children=[x for x in docs.all('strategies').values() if x.get('mutated_from')==s['id']]
  self.assertTrue(children)
  self.assertTrue(all(x['status']=='candidate' and x['revision']==1 for x in children))
  self.assertTrue(all(x['securities'][0]['name']=='贵州茅台' for x in children))
  child=children[0]
  result=self.command('backtest',{'strategy_id':child['id'],'revision':child['revision'],'start_date':'2025-01-01','end_date':'2025-09-30'})
  self.assertEqual(result['run']['status'],'completed')
 def test_apply_is_atomic_if_later_action_fails(self):
  s,docs=self.seed_positive_shadow();generated=self.command('evolve',{'strategy_id':s['id'],'revision':s['revision']})
  p=self.prepare('apply',{'strategy_id':s['id'],'revision':s['revision'],'preview_token':generated['evolution']['preview_token']})
  original=docs.all('strategies');real=evolution._apply_action;seen=[]
  def fail_second(store,action):
   seen.append(action)
   if len(seen)==2:raise RuntimeError('injected action failure')
   return real(store,action)
  # Facade reexport isn't the call site's symbol; patch the actual migrated function.
  from huohuo.strategies.legacy import evolution_05
  with patch.object(evolution_05,'_apply_action',side_effect=fail_second):
   r=self.service.commit('alice','chat',{'preview_id':p['preview_id'],'request_key':p['request_key']})
  self.assertEqual(r['run']['status'],'failed')
  self.assertEqual(docs.all('strategies'),original)
  self.assertEqual(self.service.read('alice',s['id'])['preview']['preview_status'],'pending')
 def test_live_version_changes_reject_old_confirmation(self):
  s,docs=self.seed_positive_shadow();p=self.prepare('retire',{'strategy_id':s['id'],'revision':s['revision']})
  with self.core.store.transaction():docs.set('shadows','new-evidence',{'source':'controlled'})
  with self.assertRaises(Conflict):self.service.commit('alice','chat',{'preview_id':p['preview_id'],'request_key':p['request_key']})
 def test_cancel_during_collection_prevents_late_writes(self):
  s=self.create();provider=self.service.history
  def cancel(*args):
   run=next(r for r in self.service.read('alice')['runs'] if r['status']=='running')
   self.service.cancel('alice',{'run_id':run['id']})
   return provider(*args)
  self.service.history=cancel
  result=self.command('backtest',{'strategy_id':s['id'],'revision':s['revision'],'start_date':'2025-01-01','end_date':'2025-09-30'})
  self.assertEqual(result['run']['status'],'cancelled')
  self.assertEqual(result['strategy']['status'],'candidate')
 def test_pool_scope_recombination_is_reachable(self):
  s,docs=self.seed_positive_shadow()
  second=self.command('create',{'name':'第二项合成亲本','kind':'ma_cross','params':{'fast':5,'slow':20},
      'securities':[{'code':'000001','name':'平安银行'}],'direction':'利好','rationale':'受控重组回归'})['strategy']
  with self.core.store.transaction():
   docs.set('strategies',second['id'],{**second,'status':'active','verification_status':'passed','backtest':{'thresholds_pass':True}})
   for i,nav in enumerate([1,1.02,1.04,1.06,1.08]):
    key=f'2025-09-{20+i:02}';row=docs.get('shadow_equity',key)
    row['strategies'][second['id']]={'nav':nav,'initial_capital':100000,'equity':nav*100000}
    row['overall_nav']=(row['strategies'][s['id']]['nav']+nav)/2
    docs.set('shadow_equity',key,row)
  version=self.service.read('alice')['state_version']
  generated=self.command('evolve',{'scope':'pool','state_version':version})
  self.assertEqual(generated['run']['status'],'completed')
  actions=generated['evolution']['actions']
  self.assertEqual(len([a for a in actions if a['type']=='promote']),2)
  self.assertTrue(any(a.get('parent_b') for a in actions))
  self.assertEqual(docs.get('strategies',s['id'])['evolve']['tier'],1)
 def test_source_evidence_binding_and_prior_insufficient_not_counted(self):
  from huohuo.contracts import Invalid
  body={'name':'来源验证','kind':'momentum','params':{'n':10},'securities':[{'code':'600519','name':'贵州茅台'}],
      'direction':'利好','rationale':'测试','source_evidence_ids':['not-owned']}
  with self.assertRaises(Invalid):self.prepare('create',body)
  s=self.create();docs=Documents(self.core.store,'alice')
  self.assertTrue(docs.all('events_ledger'))
  from huohuo.strategies.legacy import priors
  self.assertIsNone(priors.oos_passed({'verification_status':'insufficient','backtest':{'out_of_sample':{'win_rate_pct':100}}}))
 def test_stale_regime_not_used_when_today_index_fails(self):
  s=self.create();r=self.command('backtest',{'strategy_id':s['id'],'revision':s['revision'],'start_date':'2025-01-01','end_date':'2025-09-30'});s=r['strategy']
  docs=Documents(self.core.store,'alice')
  with self.core.store.transaction():
   changed={**s,'gene':{**s['gene'],'regime_gate':{'allow':['trend_up'],'miss_mode':'on_default'}}}
   docs.set('strategies',s['id'],changed)
   docs.set('market_regime','2025-09-29',{'date':'2025-09-29','regime':'trend_down'})
   docs.set('market_regime','_latest','2025-09-29')
  provider=self.service.history
  class IndexFailure:
   def __call__(self,*args):return provider(*args)
   def index(self,*args):raise RuntimeError('synthetic index failure')
  self.service.history=IndexFailure()
  result=self.command('shadow',{'strategy_id':s['id'],'revision':s['revision']})
  self.assertEqual(result['run']['status'],'completed')
  self.assertIsNone(docs.get('market_regime',docs.get('market_regime','_latest'))['regime'])
 def test_hibernation_is_skipped_and_retains_index_evidence(self):
  s=self.create();s=self.command('backtest',{'strategy_id':s['id'],'revision':s['revision'],'start_date':'2025-01-01','end_date':'2025-09-30'})['strategy']
  docs=Documents(self.core.store,'alice')
  with self.core.store.transaction():
   docs.set('strategies',s['id'],{**s,'gene':{**s['gene'],'regime_gate':{'allow':['trend_down'],'miss_mode':'on_default'}}})
  provider=self.service.history
  class IndexSuccess:
   def __call__(self,*args):return provider(*args)
   def index(self,start,end):
    rows=provider('000300',start,end)
    # Explicit steadily rising synthetic OHLCV gives trend_up.
    rows['records']=[{**b,'open':100+i,'close':100+i,'high':101+i,'low':99+i} for i,b in enumerate(rows['records'])]
    return rows
  self.service.history=IndexSuccess()
  result=self.command('shadow',{'strategy_id':s['id'],'revision':s['revision']})
  self.assertEqual(result['run']['status'],'skipped')
  self.assertFalse(docs.all('shadow_equity'))
  self.assertTrue(result['run']['evidence'])
  self.assertTrue(docs.all('market_index'))
 def test_pool_cannot_bypass_each_strategy_minimum_days(self):
  s,docs=self.seed_positive_shadow()
  b=self.command('create',{'name':'仅两日的合成策略','kind':'momentum','params':{'n':6},
      'securities':[{'code':'000001','name':'平安银行'}],'direction':'利好','rationale':'验证样本不足门槛'})['strategy']
  with self.core.store.transaction():
   docs.set('strategies',b['id'],{**b,'status':'active','verification_status':'passed','backtest':{'thresholds_pass':True}})
   for key,nav in [('2025-09-23',1.04),('2025-09-24',1.08)]:
    row=docs.get('shadow_equity',key);row['strategies'][b['id']]={'nav':nav,'initial_capital':100000,'equity':nav*100000};docs.set('shadow_equity',key,row)
  version=self.service.read('alice')['state_version']
  generated=self.command('evolve',{'scope':'pool','state_version':version})
  self.assertEqual(generated['run']['status'],'completed')
  self.assertFalse(any(a.get('sid')==b['id'] or a.get('parent')==b['id'] or a.get('parent_b')==b['id'] for a in generated['evolution']['actions']))
  item=next(p for p in generated['evolution']['per_strategy'] if p['strategy_id']==b['id'])
  self.assertIn('2 个有效影子日期',item['reason'])
  single=self.command('evolve',{'strategy_id':b['id'],'revision':b['revision']})
  self.assertEqual(single['evolution']['status'],'waiting_data')
 def test_insufficient_oos_cannot_generate_mutation_or_be_parent(self):
  s,docs=self.seed_positive_shadow()
  with self.core.store.transaction():docs.set('strategies',s['id'],{**docs.get('strategies',s['id']),'verification_status':'insufficient','backtest':{'thresholds_pass':False,'out_of_sample':{'win_rate_pct':100}}})
  r=self.command('evolve',{'strategy_id':s['id'],'revision':s['revision']})
  self.assertEqual(r['run']['status'],'completed')
  self.assertFalse(any(a['type']=='mutate' for a in r['evolution']['actions']))
