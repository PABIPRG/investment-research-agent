"""真实统一 HTTP 接口的类型分派、结果幂等与身份门禁。"""
import unittest
import time
import test_strategy_api as fixtures
from huohuo.strategies.schedule import DEFAULT


class UnifiedWorkerApi(unittest.TestCase):
    setUp=fixtures.StrategyApi.setUp
    tearDown=fixtures.StrategyApi.tearDown
    call=fixtures.StrategyApi.call
    def command(self,action,payload,key):
        body={'session_id':'chat','request_key':key,'action':action,'payload':payload}
        code,p=self.call('/strategies/prepare',body);self.assertEqual(code,200,p)
        code,r=self.call('/strategies/commit',{'session_id':'chat','request_key':key,'preview_id':p['preview_id']});self.assertEqual(code,200,r)
        self.assertEqual(r['run']['status'],'completed',r)
        return r
    def ready(self):
        candidate={'name':'合成统一执行','kind':'momentum','params':{'n':5},'securities':[{'code':'600519','name':'贵州茅台'}],'direction':'利好','rationale':'仅测试'}
        s=self.command('create',candidate,'create')['strategy']
        self.command('schedule',{**DEFAULT,'enabled':True,'strategy_ids':[s['id']],'event_candidates':True},'schedule')
        event={'id':'synthetic','source':'synthetic','observed_at':time.time(),'title':'合成事件','summary':'仅验收','securities':candidate['securities'],'evidence_ref':'synthetic-ref'}
        self.assertEqual(self.call('/worker/strategies/events',{'events':[event]},'test-worker')[0],200)
        code,job=self.call('/worker/claim',{'worker_id':'unified','lane':'strategy','admission_policy':'hook-model-gate-v1'},'test-worker');self.assertEqual(code,200,job)
        self.assertEqual(job['action'],'candidate')
        return job
    def test_same_result_receipt_different_result_conflict_and_trace(self):
        job=self.ready();base='/worker/attempts/'+job['attempt_id'];token=job['lease_token']
        code,_=self.call(base+'/runtime',{'session_id':'synthetic','message_id':'synthetic'},'test-worker',token);self.assertEqual(code,200)
        body={'status':'completed','candidates':[]}
        one=self.call(base+'/strategy-result',body,'test-worker',token)
        self.assertEqual(one[0],200,one)
        self.assertEqual(one,self.call(base+'/strategy-result',body,'test-worker',token))
        self.assertEqual(self.call(base+'/strategy-result',{'status':'failed','error':'different'},'test-worker',token)[0],409)
        self.assertEqual(self.call(base+'/strategy-result',body,'test-user',token)[0],403)
        self.assertEqual(self.call(base+'/strategy-result',body,'test-worker','forged')[0],409)
        with self.server.repo.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM result_outbox WHERE received=1').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM research_job_results').fetchone()[0],1)
            self.assertIsNotNone(db.execute('SELECT runtime_receipt FROM attempts WHERE id=?',(job['attempt_id'],)).fetchone()[0])
    def test_mixed_queue_keeps_existing_research_list_contract(self):
        self.ready()
        scope={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'quote_snapshot'}
        code,ex=self.call('/executions',{'request_key':'one-off','scope':scope,'question':'合成证券研究'});self.assertEqual(code,201)
        code,result=self.call('/executions');self.assertEqual(code,200)
        self.assertEqual([r['execution_id'] for r in result['executions']],[ex['execution_id']])
        code,job=self.call('/worker/claim',{'worker_id':'research','admission_policy':'hook-model-gate-v1'},'test-worker');self.assertEqual(code,200)
        self.assertEqual(job['execution_id'],ex['execution_id'])
    def test_plan_stop_revokes_existing_capability(self):
        job=self.ready();policy=self.call('/strategies')[1]['automation']
        self.command('schedule',{k:(False if k=='enabled' else policy[k]) for k in DEFAULT},'stop')
        path='/worker/attempts/'+job['attempt_id']
        self.assertEqual(self.call(path+'/heartbeat',{},'test-worker',job['lease_token'])[0],409)
        self.assertEqual(self.call(path+'/strategy-result',{'status':'completed','candidates':[]},'test-worker',job['lease_token'])[0],409)
        self.assertEqual(self.call('/strategies')[1]['planner_jobs'][0]['status'],'cancelled')

    def test_calculation_http_response_retry_returns_same_receipt(self):
        from datetime import datetime,timezone
        from test_strategy_domain import bars
        now=[datetime(2025,10,6,8,tzinfo=timezone.utc).timestamp()];calls=[]
        self.server.repo.clock=lambda:now[0];self.server.strategies.clock=lambda:now[0]
        def history(code,start,end):
            calls.append(code)
            return {'records':[r for r in bars(count=800) if start<=r['date']<=end],'source':'synthetic:http','adjustment':'qfq'}
        self.server.strategies.history=history
        s=self.command('create',{'name':'HTTP计算合成验收','kind':'momentum','params':{'n':5},'securities':[{'code':'600519','name':'贵州茅台'}],'direction':'利好','rationale':'仅回归'},'calc-create')['strategy']
        self.command('schedule',{**DEFAULT,'enabled':True,'strategy_ids':[s['id']],'actions':['backtest']},'calc-plan')
        now[0]+=3601
        code,job=self.call('/worker/claim',{'worker_id':'calculator','lane':'strategy','admission_policy':'hook-model-gate-v1'},'test-worker');self.assertEqual(code,200)
        path='/worker/attempts/'+job['attempt_id']+'/strategy-run'
        first=self.call(path,{},'test-worker',job['lease_token']);self.assertEqual(first[0],200,first)
        self.assertEqual(first[1]['run']['status'],'completed',first)
        count=len(calls)
        self.assertEqual(self.call(path,{},'test-worker',job['lease_token']),first)
        self.assertEqual(len(calls),count)
        self.assertEqual(self.call('/strategies')[1]['background_jobs'][0]['status'],'completed')
