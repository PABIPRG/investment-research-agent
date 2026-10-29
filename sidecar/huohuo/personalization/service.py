"""复用旧卡片/匹配/学习算法；正式状态按主体、版本、预览和回执保存。"""
import uuid
from datetime import datetime,timezone
from ..contracts import Invalid,text
from ..execution import Conflict,digest
from .repository import Repository
from .snapshot import Snapshot
from .legacy.runtime import runtime
from .legacy import personalize,behavior_profile,local_telemetry,risk_engine

def exact(body,required):
    if not isinstance(body,dict) or set(body)!=set(required):raise Invalid('偏好操作字段无效')

class Personalization:
    def __init__(self,store):self.store,self.repo=store,Repository(store)
    def _snapshot(self,principal):
        version,document=self.repo.load(principal)
        return version,Snapshot(self.store,principal,document)
    def _view(self,version,snap,offset=0,days=7):
        with runtime(snap.context()):
            value={'version':version,'learning':local_telemetry.local_learning_status(snap),
                   'cards':personalize.build_cards(snap,limit=20,offset=offset),
                   'matches':personalize.match_strategies(snap),
                   'profile':behavior_profile.profile_view(snap),
                   'review':local_telemetry.build_preference_review(snap,days=days),
                   'funnel':behavior_profile.behavior_funnel(snap),
                   'source_status':'ready' if snap.events else 'no_saved_events',
                   'notice':'读取本实例已保存事件；没有卡片不代表市场没有事件。学习仅影响研究兴趣排序，不改变风险偏好、策略启用、委托或交易。'}
        value['profile_is_explicit']=snap.explicit_profile
        if not snap.explicit_profile:
            value['profile']['risk_source']='not_recorded'
            value['review']['explicit_risk_profile']['source']='not_recorded'
        return value
    def read(self,principal,offset=0,days=7):
        if type(offset) is not int or not 0<=offset<=100 or type(days) is not int or days not in (7,30,90):raise Invalid('偏好查询范围无效')
        with self.repo.transaction():
            version,snap=self._snapshot(principal)
            before=snap.persistent()
            result=self._view(version,snap,offset,days)
            if snap.persistent()!=before:
                self.repo.save(principal,version+1,snap.persistent(),'retention',{},datetime.now(timezone.utc).isoformat())
                result['version']=version+1
            return result
    def _card(self,snap,cid):
        text(cid,'卡片编号',120)
        with runtime(snap.context()):
            cards=personalize.build_cards(snap,limit=100)['cards']
        card=next((c for c in cards if c['card_id']==cid),None)
        if not card:raise Invalid('卡片已不在当前资料窗口，请刷新后操作')
        return card
    def risk(self,principal):
        with self.repo.transaction():
            version,snap=self._snapshot(principal)
            with runtime(snap.context()):
                portfolio=risk_engine.portfolio_risk(snap)
                alerts=risk_engine.risk_alerts(snap)
            portfolio.update(holdings_status=snap.holdings_status,profile_is_explicit=snap.explicit_profile,
                method_version='legacy-equal-weight-shadow-v1',is_market_value=False,
                note='等权集中度与策略影子净值代理，不是实际持仓市值、实际收益或风险预测；未计现金。')
            if snap.holdings_status=='not_recorded':
                portfolio['summary'].update(n_positions=None,equal_weight=None,hhi=None)
            if not snap.explicit_profile:
                portfolio['note']+=' 风险偏好未填写，预算仅按默认稳健档示例计算，不能当作用户已确认预算。'
            return {'portfolio':portfolio,'alerts':alerts,'version':version,'profile_is_explicit':snap.explicit_profile,
                    'learning_enabled':local_telemetry.local_learning_status(snap)['enabled'],
                    'notice':'预警列表是当前记录的研究风险读模型，不自动创建连续监控或发送通知；事件可能是历史快照。'}
    def _meta(self,card):
        return {k:v for k,v in {**card.get('feedback_meta',{}),'ticker':next((x['code'] for x in card['tickers']),None),
            'industries':card.get('industries') or [],'bucket':card['bucket'],'direction':card.get('direction'),
            'event_type':card.get('type'),'strategy_id':next((x['id'] for x in card['matched']['strategies']),None)}.items() if v is not None}
    def _feedback_subject(self,snap,cid):
        if not isinstance(cid,str):raise Invalid('反馈对象编号无效')
        if cid.startswith('card-'):return self._card(snap,cid)
        with runtime(snap.context()):
            if cid.startswith('risk-'):
                item=next((r for r in risk_engine.risk_alerts(snap)['items'] if r['id']==cid),None)
                if item:return {'card_id':cid,'event_id':cid,'target_type':'risk','title':item['title'],
                    'tickers':[{'code':c} for c in item.get('codes',[])],'matched':{'strategies':[]},'bucket':'holdings',
                    'feedback_meta':{'risk_source':item['source'],'risk_severity':item['severity']}}
            elif cid.startswith('strategy:'):
                item=next((r for r in personalize.match_strategies(snap)['items'] if 'strategy:'+r['strategy_id']==cid),None)
                if item:return {'card_id':cid,'event_id':item['strategy_id'],'target_type':'strategy','title':item['name'],
                    'tickers':[{'code':c} for c in item.get('symbols',[])],'matched':{'strategies':[{'id':item['strategy_id']}]},'bucket':'strategy'}
        raise Invalid('反馈对象已不在当前研究窗口，请刷新后操作')
    def _apply(self,snap,body):
        if not isinstance(body,dict):raise Invalid('偏好操作无效')
        action=body.get('action')
        try:
            if action=='learning':
                exact(body,('action','enabled'))
                return local_telemetry.update_local_learning(snap,body['enabled'])
            if action=='clear':
                exact(body,('action',));return local_telemetry.clear_local_learning(snap)
            if action=='feedback':
                exact(body,('action','card_id','sentiment'))
                card=self._feedback_subject(snap,body['card_id'])
                return {**local_telemetry.record_feedback(snap,card['card_id'],body['sentiment'],self._meta(card)),
                        'subject':{'id':card['card_id'],'title':card['title']}}
            raise Invalid('不支持的偏好操作')
        except ValueError as e:raise Invalid(str(e)) from None
    def preview(self,principal,body):
        with self.repo.transaction():
            version,snap=self._snapshot(principal)
            before=self._view(version,snap)
            impact=self._apply(snap,body)
            pid=str(uuid.uuid4())
            self.repo.preview(pid,principal,version,snap.context_version,body)
            return {'preview_id':pid,'version':version,'payload':body,'before':before,
                    'after':self._view(version,snap),'impact':impact,'requires_confirmation':True}
    def inspect(self,principal,pid):
        with self.repo.transaction():
            p=self.repo.get_preview(principal,pid)
            body={'preview_id':pid,'request_key':pid}
            receipt=self.repo.receipt(principal,pid,body)
            if receipt is not None:return {'preview_id':pid,'receipt':receipt}
            version,snap=self._snapshot(principal)
            if version!=p['version'] or snap.context_version!=p['context_version']:raise Conflict('偏好、投资事实或事件已变化，请重新预览')
            before=self._view(version,snap);impact=self._apply(snap,p['payload'])
            return {'preview_id':pid,'payload':p['payload'],'before':before,'after':self._view(version,snap),'impact':impact}
    def commit(self,principal,body):
        exact(body,('preview_id','request_key'));text(body['request_key'],'请求标识',200)
        if body['request_key']!=body['preview_id']:raise Invalid('保存须复用原预览标识')
        with self.repo.transaction():
            old=self.repo.receipt(principal,body['request_key'],body)
            if old is not None:return old
            p=self.repo.get_preview(principal,body['preview_id'])
            version,snap=self._snapshot(principal)
            if version!=p['version'] or snap.context_version!=p['context_version']:raise Conflict('偏好、投资事实或事件已变化，请重新预览')
            result=self._apply(snap,p['payload'])
            if p['payload']['action']=='clear':self.repo.purge_learning_history(principal,p['id'])
            self.repo.save(principal,version+1,snap.persistent(),p['payload']['action'],p['payload'],datetime.now(timezone.utc).isoformat())
            receipt={'saved':True,'version':version+1,'impact':result}
            self.repo.record_receipt(principal,body['request_key'],body,receipt)
            return receipt
    def record(self,principal,body):
        if not isinstance(body,dict):raise Invalid('阅读行为请求无效')
        exact(body,('request_key','session_id','card_id','action','surface') if 'surface' in body else ('request_key','session_id','card_id','action'))
        surface=body.get('surface','dashboard')
        if surface not in ('dashboard','assistant'):raise Invalid('阅读行为入口无效')
        key=text(body['request_key'],'事件标识',80);text(body['session_id'],'会话',80)
        if body['action'] not in ('impression','open','analyze'):raise Invalid('不支持的阅读行为')
        with self.repo.transaction():
            old=self.repo.receipt(principal,key,body)
            if old is not None:return old
            version,snap=self._snapshot(principal)
            card=self._feedback_subject(snap,body['card_id'])
            result=local_telemetry.record_events(snap,[{'schema_version':1,'event_id':'reading:'+digest(key)[:40],
                'session_id':body['session_id'],'surface':surface,'target_type':card.get('target_type','event'),'target_id':card['event_id'],
                'action':body['action'],'context':self._meta(card)}])
            if result.get('stored'):
                self.repo.save(principal,version+1,snap.persistent(),'reading',{'card_id':card['card_id'],'action':body['action']},datetime.now(timezone.utc).isoformat())
            self.repo.record_receipt(principal,key,body,result)
            return result
    def refresh_sources(self,principal,market,repository):
        from ..investment.service import Investment
        from ..strategies.news_source import source
        facts=Investment(self.store).read(principal)
        codes={x['ticker']:x for x in facts['holdings']+facts['watchlist']}
        securities=[]
        for code in sorted(codes)[:20]:
            # 新闻适配器当前只支持沪深 A 股；其他持仓保留明确缺口。
            exchange='SSE' if code.startswith(('600','601','603','605','688','689')) else 'SZSE' if code.startswith(('000','001','002','003','300','301')) else None
            if exchange:securities.append({'code':code,'name':codes[code].get('display_name') or codes[code].get('name') or code,'exchange':exchange})
        if not securities:return {'status':'unavailable','count':0,'notice':'尚无可查询的沪深 A 股持仓或自选；不会自动扩大查询范围。'}
        events=source(market,repository,principal)(securities)
        from ..contracts import canonical
        with self.repo.transaction():
            for event in events:
                self.store._connect().execute('INSERT OR IGNORE INTO strategy_events VALUES(?,?,?,?,?)',
                    (principal,event['id'],digest(event),canonical(event),event['observed_at']))
        return {'status':'ok','count':len(events),'coverage':len(securities),'requested_codes':len(codes),
                'notice':'本次读取已记录沪深 A 股的最新相关资讯，最多20只；不创建持续委托或通知。相关性和事件方向需研究核对。'}
