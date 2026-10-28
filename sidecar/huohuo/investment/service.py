"""统一投资事实服务：有版本快照、预览回执、原子审计与持久事实事件。"""
import copy
import json
import math
import re
import uuid
from datetime import datetime, timezone
from ..contracts import Invalid, canonical, text
from ..execution import Conflict, Missing, digest
from .document import Document
from .manual_trades import ManualTradeRequest, apply_trade
from .trade_revisions import TradeRevisionRequest, apply_revision
from .portfolio_performance import _snapshot
from .instruments import instrument, identity, annotate
from .analysis import cost_analysis
from .names import recorded_names, trade_metadata, restore_names, display_rows
from .risk_questionnaire import questionnaire, score as score_risk
from .risk_preferences import adjust as adjust_risk, policy as risk_policy, parse as parse_risk
from ..position_risk.configuration import apply as apply_position_risk,document as position_config

EMPTY = {'default': [], 'watchlist': [], 'manual_trades': [], 'snapshots': [], 'trade_revisions': [], 'corrections': [], 'holdings_recorded': False, 'watchlist_recorded': False}

def now(): return datetime.now(timezone.utc).isoformat()
def exact(body, keys):
    if not isinstance(body,dict) or set(body)!=set(keys): raise Invalid('请求包含未允许字段或缺少字段')
def ticker(value):
    instrument(value)
    return value

def number(value, label, nullable=False):
    if nullable and value is None:return None
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or value>1e12:raise Invalid(label+'须为 0 至 1万亿的有限数值')
    return value

class Investment:
    def __init__(self,store):self.store=store
    def _load(self,principal):
        row=self.store._connect().execute('SELECT * FROM investment_facts WHERE principal=?',(principal,)).fetchone()
        return (row['version'],json.loads(row['document']),row['updated_at']) if row else (0,copy.deepcopy(EMPTY),None)
    def _view(self,version,document,updated):
        names=recorded_names(document)
        holdings=display_rows(document['default'],names)
        return {'version':version,'status':'recorded' if version else 'not_recorded','updated_at':updated,
                'holdings_status':'recorded' if document.get('holdings_recorded') else 'not_recorded','watchlist_status':'recorded' if document.get('watchlist_recorded') else 'not_recorded',
                'holdings':holdings,'watchlist':display_rows(document['watchlist'],names),'trades':display_rows(document['manual_trades'],names),
                'revisions':document['trade_revisions'],'corrections':document['corrections'],
                'risk_profile':copy.deepcopy(document.get('risk_profile')), 'risk_questionnaire':questionnaire(),
                'risk_policy':risk_policy(document.get('risk_profile')),
                'risk_profile_history':copy.deepcopy(document.get('risk_profile_history', [])),
                'cost_analysis':cost_analysis([{**x,'name':x['display_name']} for x in holdings],document.get('holdings_recorded',False))}
    def read(self,principal):
        version,document,updated=self._load(principal)
        value=self._view(version,document,updated)
        if getattr(self.store,'position_risk',None):value['position_risk']=self.store.position_risk.view(principal,document)
        return value
    def parse_risk(self,body):return parse_risk(body)
    def _risk_effects(self,principal,before,after,result):
        position=getattr(self.store,'position_risk',None)
        effects=position.effects(principal,before,after) if position else []
        if effects:result['position_risk_impact']=effects
        return result
    def snapshot(self,principal,version):
        if type(version) is not int or version<0:raise Invalid('事实版本无效')
        if version==0:return self._view(0,copy.deepcopy(EMPTY),None)
        row=self.store._connect().execute('SELECT * FROM investment_versions WHERE principal=? AND version=?',(principal,version)).fetchone()
        if not row:raise Missing('事实快照不存在')
        return self._view(version,json.loads(row['document']),row['recorded_at'])
    def _apply(self,document,command,payload):
        doc=Document(document)
        try:
            if command in ('trade','revision'):
                if not isinstance(payload,dict) or {'action','version'} & set(payload):raise Invalid('仅接受业务字段')
                code=payload.get('ticker')
                if command=='revision':
                    original=next((x for x in document['manual_trades'] if x['request_id']==payload.get('trade_request_id')),None)
                    if original:code=original['ticker']
                if code:ticker(code)
                if payload.get('ticker'):ticker(payload['ticker'])
                if payload.get('affects_holdings',True) and any(x['ticker']==code and x['cost_price'] is None for x in document['default']):raise Invalid('当前成本未知，请先校正成本，或选择只补记录')
                # 旧纯算法以数值规范化持仓；未知成本仅在不参与计算时临时投影，随后恢复。
                unknown={x['ticker'] for x in doc.value['default'] if x['cost_price'] is None}
                for x in doc.value['default']:
                    if x['ticker'] in unknown:x['cost_price']=0
                import hashlib
                version=hashlib.sha256(json.dumps(doc.value,sort_keys=True,default=str).encode()).hexdigest()
                model=ManualTradeRequest if command=='trade' else TradeRevisionRequest
                request_payload,name=trade_metadata(document,command,payload)
                request=model(**request_payload,action='commit',version=version)
                result=(apply_trade(doc,request) if command=='trade' else apply_revision(doc,request))
                for x in doc.value['default']:
                    if x['ticker'] in unknown:x['cost_price']=None
                restore_names(doc.value,document,command,payload,name,result)
                doc.value.pop('investment_outbox',None) # 正式 outbox 由外层同事务规范化，禁止双发。
                if command=='revision' and not payload.get('affects_holdings',True) and code in unknown:
                    # 只修订记录没有成本计算；预览和审计都不能把未知成本显示成零。
                    impact=result['impact']
                    impact['current']['cost_price']=None
                    impact['projected']['cost_price']=None
                    impact['delta_cost_price']=None
                result['holdings']=doc.value['default']
            elif command=='holding':
                exact(payload,('ticker','name','quantity','cost_price','effective_at','reason'))
                code=ticker(payload['ticker']);name=text(payload['name'],'证券名称',100);reason=text(payload['reason'],'校正原因',500)
                qty=number(payload['quantity'],'数量');cost=number(payload['cost_price'],'成本',True)
                at=datetime.fromisoformat(payload['effective_at'])
                if at.tzinfo is None or at>datetime.now(timezone.utc):raise Invalid('确认时间须包含时区且不能晚于当前')
                before=next((x for x in document['default'] if x['ticker']==code),None)
                after={'ticker':code,'name':name,'quantity':qty,'cost_price':cost,'position_time':at.isoformat(),'time_source':'user_modified'} if qty else None
                doc.value['default']=[x for x in document['default'] if x['ticker']!=code]+([after] if after else [])
                correction={'ticker':code,'name':name,'before':before,'after':after,'effective_at':at.isoformat(),'recorded_at':now(),'reason':reason}
                doc.value['corrections'].append(correction)
                doc.value['snapshots'].append(_snapshot(doc.value['default'],'manual',at.isoformat(),document['snapshots'][-1]['snapshot_id'] if document['snapshots'] else None))
                result={'holdings':doc.value['default'],'correction':correction,'gaps':[]}
            elif command=='watchlist':
                exact(payload,('ticker','name','reason','remove'))
                code=ticker(payload['ticker']);text(payload['name'],'证券名称',100)
                if type(payload['remove']) is not bool:raise Invalid('移除标记无效')
                if not isinstance(payload['reason'],str) or len(payload['reason'])>500:raise Invalid('关注原因过长')
                old=next((x for x in document['watchlist'] if x['ticker']==code),None)
                doc.value['watchlist']=[x for x in document['watchlist'] if x['ticker']!=code]
                if not payload['remove']:doc.value['watchlist'].append({'ticker':code,'name':payload['name'],'reason':payload['reason'],'added_at':old['added_at'] if old else now()})
                result={'watchlist':doc.value['watchlist'],'gaps':[]}
            elif command=='risk_profile':
                result=score_risk(payload)
                result['inferred_profile']=result['profile']
                doc.value['risk_profile']=result
            elif command=='risk_adjust':
                result=adjust_risk(document.get('risk_profile'),payload)
                doc.value['risk_profile']=result
            elif command=='position_risk':
                settings,result=apply_position_risk(document,payload)
                doc.value['position_risk']=settings
            else:raise Invalid('不支持的投资操作')
        except ValueError as e:raise Invalid(str(e)) from e
        if command in ('holding','trade','revision') and (command=='holding' or payload.get('affects_holdings',True)):doc.value['holdings_recorded']=True
        if command=='watchlist':doc.value['watchlist_recorded']=True
        return doc.value,result
    def preview(self,principal,body):
        exact(body,('command','payload'))
        with self.store.transaction():
            version,document,_=self._load(principal)
            after,result=self._apply(document,body['command'],body['payload'])
            result=self._risk_effects(principal,document,after,result)
            pid=str(uuid.uuid4())
            self.store._connect().execute('INSERT INTO investment_previews VALUES(?,?,?,?,?,?)',(principal,pid,version,body['command'],canonical(body['payload']),canonical(result)))
            return {'preview_id':pid,'fact_version':version,'command':body['command'],'payload':copy.deepcopy(body['payload']),
                    'before':self._view(version,document,None),'after':self._view(version,after,None),'impact':result,
                    'notice':result['notice'] if body['command']=='position_risk' else '确认后按已明确配置的持仓风险约定更新对应委托；不下单。' if result.get('position_risk_impact') else '仅预览；确认后更新投资事实，不创建或终止委托。'}
    def inspect_preview(self,principal,pid):
        text(pid,'预览编号',100)
        with self.store.transaction():
            db=self.store._connect()
            p=db.execute('SELECT * FROM investment_previews WHERE principal=? AND preview_id=?',(principal,pid)).fetchone()
            if not p:raise Missing('预览不存在或不属于当前用户')
            receipt=db.execute('SELECT receipt FROM investment_receipts WHERE principal=? AND request_key=?',(principal,pid)).fetchone()
            if receipt:return {'preview_id':pid,'receipt':json.loads(receipt['receipt'])}
            version,document,_=self._load(principal)
            if version!=p['version']:raise Conflict('事实版本已变化，请重新预览')
            payload=json.loads(p['payload']);after,result=self._apply(document,p['command'],payload)
            result=self._risk_effects(principal,document,after,result)
            return {'preview_id':pid,'fact_version':version,'command':p['command'],'payload':payload,'before':self._view(version,document,None),'after':self._view(version,after,None),'impact':result}
    def commit(self,principal,body):
        exact(body,('preview_id','request_key'));key=text(body['request_key'],'请求标识',200)
        with self.store.transaction():
            db=self.store._connect();fingerprint=digest(body)
            old=db.execute('SELECT * FROM investment_receipts WHERE principal=? AND request_key=?',(principal,key)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint:raise Conflict('请求标识已用于不同操作')
                return json.loads(old['receipt'])
            p=db.execute('SELECT * FROM investment_previews WHERE principal=? AND preview_id=?',(principal,body['preview_id'])).fetchone()
            if not p:raise Missing('预览不存在，请重新预览')
            version,document,_=self._load(principal)
            if version!=p['version']:raise Conflict('事实版本已变化，请刷新并重新预览；原输入已保留。')
            payload=json.loads(p['payload']);after,result=self._apply(document,p['command'],payload)
            if after==document:
                receipt={'saved':True,'facts':self.read(principal),'duplicate':True}
                db.execute('INSERT INTO investment_receipts VALUES(?,?,?,?)',(principal,key,fingerprint,canonical(receipt)))
                return receipt
            version+=1;at=now()
            if p['command'] in ('risk_profile','risk_adjust'):
                after['risk_profile']['recorded_at']=at
                after.setdefault('risk_profile_history',[]).append({**copy.deepcopy(after['risk_profile']),'fact_version':version})
            encoded=canonical(after)
            db.execute('INSERT INTO investment_facts VALUES(?,?,?,?) ON CONFLICT(principal) DO UPDATE SET version=excluded.version,document=excluded.document,updated_at=excluded.updated_at',(principal,version,encoded,at))
            db.execute('INSERT INTO investment_versions VALUES(?,?,?,?)',(principal,version,encoded,at))
            db.execute('INSERT INTO investment_audit VALUES(?,?,?,?,?)',(principal,version,p['command'],p['payload'],at))
            if p['command'] in ('holding','trade','revision','position_risk') and getattr(self.store,'position_risk',None):
                self.store.position_risk.reconcile(principal,after)
            if p['command']=='position_risk':
                receipt={'saved':True,'facts':self.read(principal),'impact':result}
                db.execute('INSERT INTO investment_receipts VALUES(?,?,?,?)',(principal,key,fingerprint,canonical(receipt)))
                return receipt
            if p['command'] in ('risk_profile','risk_adjust'):
                # 偏好不改变证券事实，不创建委托或唤醒持仓／自选订阅。
                receipt={'saved':True,'facts':self._view(version,after,at),'impact':result}
                db.execute('INSERT INTO investment_receipts VALUES(?,?,?,?)',(principal,key,fingerprint,canonical(receipt)))
                return receipt
            codes=sorted({x['ticker'] for x in after['default']+document['default']+after['watchlist']+document['watchlist']})
            code=payload.get('ticker') or result.get('entry',{}).get('ticker')
            event_id='investment:'+digest([principal,version])
            event={'event_id':event_id,'hook_type':'investment.facts_revised','schema_version':'1','producer':'huohuo-investment','occurred_at':at,'observed_at':at,'subject_ids':[identity(x) for x in ([code] if code else codes)],'source_version':str(version),'content_hash':digest(after),'payload':{'principal_id':principal,'fact_version':version,'previous_version':version-1,'change_type':p['command'],'feature_key':'watchlist' if p['command']=='watchlist' else 'holding:'+str(code),'ticker':code,'changed_fields':list(payload)}}
            db.execute('INSERT INTO investment_outbox VALUES(?,?,?,?,0)',(event_id,principal,version,canonical(event)))
            receipt={'saved':True,'facts':self._view(version,after,at),'event_id':event_id,'impact':result}
            db.execute('INSERT INTO investment_receipts VALUES(?,?,?,?)',(principal,key,fingerprint,canonical(receipt)))
            return receipt
