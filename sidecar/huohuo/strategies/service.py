"""策略正式状态与确认凭证；所有业务变更在当前实例内持久化。"""
import json
import time
import uuid
from datetime import datetime,timezone
from ..contracts import Invalid,canonical,text
from ..execution import Conflict,Missing,digest
from .storage import Documents
from .validation import exact,validate,identifier
from .history import History
from .confirmation import action_summary,rule_text
from .legacy import evolution,priors
from .legacy.runtime import runtime

LABELS={'create':'保存研究策略','backtest':'运行回测','shadow':'更新影子验证','evolve':'生成进化预案','apply':'应用进化预案','retire':'停止策略验证'}
class Strategies:
    def __init__(self,store,history=None,clock=time.time,event_source=None):
        self.store,self.history,self.clock=store,history or History(),clock
        self.event_source=event_source
        self.store.strategies=self
        from ..research_partner.strategy_tasks import StrategyTasks
        self.tasks=StrategyTasks(self)
        from ..research_partner.strategy_upgrade import migrate
        migrate(self)
    def today(self):
        from zoneinfo import ZoneInfo
        now=datetime.fromtimestamp(self.clock(),ZoneInfo('Asia/Shanghai'))
        # Intraday bars are not completed evidence. Yesterday includes the last actual trading day via source.
        from datetime import timedelta
        return now.date() if now.hour>=16 else now.date()-timedelta(days=1)
    def recovery(self):
        from .background import recover
        recover(self)
        with self.store.transaction():
            self.store._connect().execute("UPDATE strategy_runs SET status='interrupted',error='产品重启中断本次计算，请核对后明确重试',updated_at=? WHERE status='running'",(self.clock(),))
            self.store._connect().execute("UPDATE strategy_previews SET status='interrupted' WHERE status='running'")
    def owned(self,docs,sid):
        identifier(sid);record=docs.get('strategies',sid)
        if not record:raise Missing('策略不存在')
        return record
    def read(self,principal,sid=None,request_key=None):
        with self.store.read_snapshot(),runtime(self.clock):
            docs=Documents(self.store,principal)
            records=[self.owned(docs,sid)] if sid is not None else list(docs.all('strategies').values())
            if request_key is not None:text(request_key,'请求标识',200)
            rows=self.store._connect().execute('SELECT * FROM strategy_runs WHERE principal=?'+(' AND EXISTS (SELECT 1 FROM strategy_run_subjects x WHERE x.run_id=strategy_runs.id AND x.principal=strategy_runs.principal AND x.strategy_id=?)' if sid is not None else '')+(' AND request_key=?' if request_key is not None else '')+' ORDER BY created_at DESC,id DESC LIMIT 30',(principal,)+((sid,) if sid is not None else ())+((request_key,) if request_key is not None else ())).fetchall()
            from . import schedule,suggestions
            automation=schedule.read(self,principal)
            pool=evolution.status(docs,sid,include_history=False)
            pool.update(closed_loop_enabled=automation['enabled'],closed_loop_time=automation['daily_time'],next_scheduled_run_at=automation['next_at'])
            jobs=self.tasks.views(principal)
            planner=self.tasks.views(principal,candidates=True)
            return {'background_jobs':jobs,'planner_jobs':planner,'automation':automation,'suggestions':suggestions.list_pending(self,principal),'priors':priors.build_hint(docs),'strategies':records,'pool':pool,
                'attribution':evolution.attribution(docs,sid),'preview':evolution.current_preview(docs,sid),
                'runs':[self.run_view(r) for r in rows],
                'previews':{s['id']:evolution.current_preview(docs,s['id']) for s in records},
                'state_version':docs.version(),'mode':'scheduled' if automation['enabled'] else 'on_demand','model_note':__import__(__package__+'.calculations',fromlist=['MODEL_NOTE']).MODEL_NOTE}
    def run_view(self,row):
        result=json.loads(row['result']) if row['result'] else None
        subjects=[r[0] for r in self.store._connect().execute('SELECT strategy_id FROM strategy_run_subjects WHERE run_id=? AND principal=? ORDER BY strategy_id',(row['id'],row['principal']))]
        return {'execution_id':row['execution_id'],'subjects':subjects,'id':row['id'],'strategy_id':row['strategy_id'],'request_key':row['request_key'],'action':row['action'],
            'status':row['status'],'created_at':row['created_at'],'updated_at':row['updated_at'],
            'error':row['error'],'evidence':(result or {}).get('evidence',[]),'result':result}
    def prepare(self,principal,session,body):
        exact(body,('request_key','action','payload'));text(session,'会话',200);text(body['request_key'],'请求标识',200)
        action=body['action'];payload=validate(action,body['payload'],self.today())
        fp=digest(body)
        with self.store.transaction(),runtime(self.clock):
            db=self.store._connect();docs=Documents(self.store,principal)
            old=db.execute('SELECT * FROM strategy_previews WHERE principal=? AND session=? AND request_key=?',(principal,session,body['request_key'])).fetchone()
            if old:
                if old['fingerprint']!=fp:raise Conflict('同一请求标识不能更改内容')
                return self.preview_view(old)
            if action=='schedule':
                from .schedule import prepare
                summary=prepare(self,docs,payload)
            elif action=='accept_suggestion':
                from .suggestions import prepare
                suggestion,candidate=prepare(self,docs,payload)
                origin='归档召回' if suggestion['source_kind']=='archive' else '事件研究'
                names='、'.join(s['name']+'（'+s['code']+'）' for s in candidate['securities'])
                summary=f"保存{origin}候选：{candidate['name']}；证券：{names}；规则：{rule_text(candidate['kind'],candidate['params'])}；方向：{candidate['direction']}。仍需回测验证，不进行交易，也不自动加入后台计划。"
            elif action=='create':
                sources=[]
                for evidence_id in payload['source_evidence_ids']:
                    source=db.execute('SELECT tool_id,result FROM research_tool_calls WHERE id=? AND principal=? AND session=?',(evidence_id,principal,session)).fetchone()
                    if not source or not source['result'] or json.loads(source['result']).get('status')!='ok':raise Invalid('来源证据不属于本对话或没有有效结果')
                    sources.append({'id':evidence_id,'tool':source['tool_id']})
                payload['source_refs']=sources
                if docs.get('strategies',payload['id']):raise Conflict('同一规则与证券的策略已存在，请查看现有策略')
                if len(docs.all('strategies'))>=100:raise Invalid('当前实例最多保存 100 项策略')
                summary=f"{payload['name']}；{'、'.join(s['name']+'（'+s['code']+'）' for s in payload['securities'])}；规则 {rule_text(payload['kind'],payload['params'])}。保存为待验证候选，不进行真实交易。"
            elif payload.get('scope')=='pool':
                if payload['state_version']!=docs.version():raise Conflict('策略池已更新，请刷新后重新预览')
                if not docs.all('strategies'):raise Invalid('请先建立策略并积累验证记录')
                summary=f"{LABELS[action]}；范围为当前用户的整个策略池，按全部有效影子证据进行同批比较。"
                if action=='apply':
                    preview=evolution.current_preview(docs)
                    if not preview.get('valid') or preview.get('preview_token')!=payload['preview_token'] or not preview.get('actions'):raise Conflict('没有可应用的有效全池预案')
                    summary+=' 精确动作：'+action_summary(docs,preview['actions'])
            else:
                current=self.owned(docs,payload['strategy_id'])
                if current['revision']!=payload['revision']:raise Conflict('策略已更新，请刷新后重新预览')
                if action=='shadow' and current['status']!='active':raise Invalid('先完成一次有效回测，才可开始影子验证')
                summary=f"{current['name']}；{LABELS[action]}；当前版本 {current['revision']}。"
                if action=='backtest':summary+=f" {payload['start_date']} 至 {payload['end_date']}，样本外 30%，不含费用与滑点。"
                if action=='shadow':summary+='只更新当前已完成日线的模拟记录，不补造过去的影子收益。'
                if action=='apply':
                    preview=evolution.current_preview(docs,current['id'])
                    if not preview.get('valid') or preview.get('preview_token')!=payload['preview_token'] or not preview.get('actions'):raise Conflict('没有可应用的有效预案')
                    summary+=' 将应用以下精确动作：'+action_summary(docs,preview['actions'])
            pid='SPV_'+uuid.uuid4().hex
            db.execute('INSERT INTO strategy_previews VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (pid,principal,session,body['request_key'],fp,action,canonical({'command':payload,'summary':summary}),docs.version(),self.clock()+1800,'pending',None))
            return self.preview_view(db.execute('SELECT * FROM strategy_previews WHERE id=?',(pid,)).fetchone())
    @staticmethod
    def preview_view(row):
        payload=json.loads(row['payload'])
        return {'preview_id':row['id'],'request_key':row['request_key'],'action':row['action'],
            'summary':payload['summary'],'expires_at':row['expires_at'],'status':row['status'],
            'requires_confirmation':True}
    def commit(self,principal,session,body):
        from .workflow import execute
        exact(body,('preview_id','request_key'));text(body['preview_id'],'确认凭证',100)
        with self.store.transaction(),runtime(self.clock):
            db=self.store._connect();docs=Documents(self.store,principal)
            row=db.execute('SELECT * FROM strategy_previews WHERE id=? AND principal=? AND session=?',(body['preview_id'],principal,session)).fetchone()
            if not row:raise Missing('确认凭证不存在')
            if row['request_key']!=body['request_key']:raise Conflict('请求标识不匹配')
            if row['result']:return json.loads(row['result'])
            if row['status']!='pending':raise Conflict('本请求已开始或已中断，请查询运行记录，不要重复提交')
            if self.clock()>row['expires_at'] or docs.version()!=row['state_version']:raise Conflict('预览已过期或策略数据已更新，请重新预览确认')
            db.execute("UPDATE strategy_previews SET status='running' WHERE id=?",(row['id'],))
            run='SRN_'+uuid.uuid4().hex;payload=json.loads(row['payload'])['command']
            sid=payload['id'] if row['action']=='create' else payload.get('strategy_id','strategy_pool')
            if row['action']=='schedule':sid='strategy_plan'
            if row['action']=='accept_suggestion':
                from .suggestions import prepare
                _,candidate=prepare(self,docs,payload);sid=candidate['id']
            db.execute('INSERT INTO strategy_runs(id,principal,strategy_id,request_key,action,status,created_at,updated_at,source_version,result,error) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (run,principal,sid,row['request_key'],row['action'],'running',self.clock(),self.clock(),row['state_version'],None,None))
            subjects=list(docs.all('strategies')) if payload.get('scope')=='pool' else payload['strategy_ids'] if row['action']=='schedule' else [sid]
            for subject in subjects:db.execute('INSERT INTO strategy_run_subjects VALUES(?,?,?)',(run,principal,subject))
        return execute(self,docs,row,run,payload)
    def cancel(self,principal,body):
        exact(body,('run_id',));text(body['run_id'],'运行标识',100)
        with self.store.transaction():
            db=self.store._connect();r=db.execute('SELECT * FROM strategy_runs WHERE id=? AND principal=?',(body['run_id'],principal)).fetchone()
            if not r:raise Missing('运行记录不存在')
            if r['execution_id'] and r['status']=='running': self.tasks.repo.cancel_job(principal,r['execution_id'])
            if r['status']=='running':db.execute("UPDATE strategy_runs SET status='cancelled',error='用户停止本次计算；迟到结果不会写入策略',updated_at=? WHERE id=?",(self.clock(),r['id']))
            return self.run_view(db.execute('SELECT * FROM strategy_runs WHERE id=?',(r['id'],)).fetchone())

    def background_tick(self,principal):
        from .background import tick
        return tick(self,principal)
    def ingest_events(self,principal,events):
        from .planner import ingest
        return ingest(self,principal,events)
    def planner_claim(self,principal,worker_id):
        from .planner import claim
        return claim(self,principal,worker_id)
    def planner_heartbeat(self,principal,job_id,token):
        from .planner import heartbeat
        return heartbeat(self,principal,job_id,token)
    def planner_finish(self,principal,job_id,token,result):
        from .planner import finish
        return finish(self,principal,job_id,token,result)
