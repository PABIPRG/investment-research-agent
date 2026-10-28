import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone
from huohuo.execution import Repository,Conflict
from huohuo.mandates import Mandates
from huohuo.contracts import Invalid

class PositionRiskInheritanceTest(unittest.TestCase):
    def test_program_execution_uses_core_evidence_and_target_consumes_once(self):
        from types import SimpleNamespace
        from zoneinfo import ZoneInfo
        from huohuo.market.service import MarketData
        from huohuo.market.contracts import envelope,UNITS
        from huohuo.position_risk.execution import run
        self.t=datetime(2026,10,28,11,0,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        self.repo.clock=lambda:self.t
        self.price=12
        stamp=lambda:datetime.fromtimestamp(self.t,timezone.utc).isoformat()
        def provider(request):
            return envelope('synthetic:position-risk',{'items':[{'code':c,'name':'合成公司','price':self.price,'previous_close':10,
                'pct_change':20,'volume_ratio':1,'turnover':2,'amount_yi':3,'volume':1000,'units':dict(UNITS),'as_of':stamp(),'time_known':True}
                for c in request['codes']]},as_of=stamp())
        market=MarketData(provider,clock=lambda:self.t,now=stamp)
        calendar=SimpleNamespace(is_trading_day=lambda day:True)
        self.core.service.calendar=calendar
        server=SimpleNamespace(repo=self.repo,mandates=self.core,market=market,calendar=calendar,config={'principal':'owner'})
        self.core.notifications.save('owner',{'expected_revision':0,'enabled':True,'timezone':'Asia/Shanghai','quiet_hours':None,'channels':['app']})
        self.save_global();self.core.tick()
        count=0
        while job:=self.repo.claim('program-test'):
            result=run(server,job['attempt_id'],job['lease_token'])
            self.assertEqual(result['status'],'succeeded');count+=1
        self.assertEqual(count,2)
        self.core.tick()
        plans=self.core.position_risk.view('owner')['plans'][0]
        tp=plans['targets']['take_profit']['mandate_id']
        view=self.core.get('owner',tp)
        self.assertEqual(len([d for d in view['decisions'] if d['decision']=='send']),1)
        self.assertEqual(self.core.position_risk.reason(tp),'position_target_consumed')
        self.assertEqual(len(view['notifications']),1)
        # 同一代次的新任务即使再次命中也不能重复取得发送资格。
        self.core.tick()
        self.assertEqual(len(self.core.get('owner',tp)['notifications']),1)
        self.assertTrue(self.repo.evidence('owner',view['executions'][0]['execution_id']))
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.repo=Repository(Path(self.tmp.name)/'db.sqlite')
        self.core=Mandates(self.repo,'test');self.inv=self.core.investment
        self.holding(10)
    def tearDown(self):self.core.store.close();self.tmp.cleanup()
    def commit(self,body):
        p=self.inv.preview('owner',body)
        return self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']})
    def holding(self,cost,quantity=100):
        return self.commit({'command':'holding','payload':{'ticker':'600519','name':'合成公司','cost_price':cost,'quantity':quantity,
            'effective_at':datetime.now(timezone.utc).isoformat(),'reason':'合成持仓'}})
    def config(self,**extra):
        return {'take_profit':{'enabled':True,'mode':'percent','value':.12},'stop_loss':{'enabled':True,'mode':'percent','value':.06},'effective_at':None,'expires_at':None,'monitoring_disabled':False,**extra}
    def save_global(self,**extra):return self.commit({'command':'position_risk','payload':{'operation':'global','config':self.config(**extra)}})
    def test_preview_confirm_core_mandates_and_frozen_cost_rearm(self):
        p=self.inv.preview('owner',{'command':'position_risk','payload':{'operation':'global','config':self.config()}})
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM mandates').fetchone()[0],0)
        result=self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']})
        self.assertEqual(self.inv.commit('owner',{'preview_id':p['preview_id'],'request_key':p['preview_id']}),result)
        plans=self.core.position_risk.view('owner')['plans'];take=plans[0]['targets']['take_profit']
        self.assertAlmostEqual(take['resolved_price'],11.2)
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM mandates').fetchone()[0],2)
        self.holding(12)
        view=self.core.position_risk.view('owner')['plans'][0]
        self.assertTrue(view['basis_changed'])
        self.assertEqual(view['targets']['take_profit']['basis_cost'],10)
        self.commit({'command':'position_risk','payload':{'operation':'rearm','ticker':'600519','kind':'take_profit'}})
        new=self.core.position_risk.view('owner')['plans'][0]['targets']['take_profit']
        self.assertAlmostEqual(new['resolved_price'],13.44)
        self.assertNotEqual(new['mandate_id'],take['mandate_id'])
        self.assertEqual(self.core.get('owner',take['mandate_id'])['mandate']['status'],'ended')
        self.assertGreater(new['generation'],take['generation'])
    def test_override_disable_remove_and_sellout_revoke_old_generation(self):
        self.save_global()
        old=self.core.position_risk.view('owner')['plans'][0]['targets']['stop_loss']['mandate_id']
        self.commit({'command':'position_risk','payload':{'operation':'override','ticker':'600519','config':self.config(monitoring_disabled=True)}})
        self.assertEqual(self.core.get('owner',old)['mandate']['status'],'ended')
        self.assertEqual(self.core.position_risk.view('owner')['plans'][0]['status'],'disabled')
        self.commit({'command':'position_risk','payload':{'operation':'remove_override','ticker':'600519'}})
        target=self.core.position_risk.view('owner')['plans'][0]['targets']['stop_loss']
        self.holding(None)
        self.assertEqual(self.core.get('owner',target['mandate_id'])['mandate']['status'],'ended')
        self.assertEqual(self.core.position_risk.view('owner')['plans'][0]['status'],'cost_unknown')
        self.holding(10);new=self.core.position_risk.view('owner')['plans'][0]['targets']['stop_loss']
        self.holding(10,0)
        self.assertEqual(self.core.get('owner',new['mandate_id'])['mandate']['status'],'ended')
    def test_profiles_do_not_auto_create_rules_and_invalid_config_is_atomic(self):
        bank=self.inv.read('owner')['risk_questionnaire']['quick']
        self.commit({'command':'risk_profile','payload':{'tier':'quick','answers':[{'qid':q['qid'],'option':0} for q in bank]}})
        self.assertEqual(self.core.store._connect().execute('SELECT count(*) FROM mandates').fetchone()[0],0)
        for value in (True,float('nan'),0,-1):
            with self.subTest(value=value),self.assertRaises(Invalid):self.save_global(stop_loss={'enabled':True,'mode':'percent','value':value})
        with self.assertRaises(Invalid):self.save_global(stop_loss={'enabled':True,'mode':'percent','value':1})
        self.assertIsNone(self.core.position_risk.view('owner')['config']['global'])
