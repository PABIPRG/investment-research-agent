"""DSH 结构化研究建议的确定性画像校准；结果复用研究证据台账。

模型拥有分析和原建议，程序绑定当前主体、证券、证据、画像版本及保存时间。
不把校准结果写成投资事实、委托、持仓或交易，也不以缺失资料推断持有。
"""
import copy
import json
import math
from datetime import datetime, timezone
from .contracts import Invalid, canonical, text
from .execution import Conflict, digest
from .investment.risk_profiles import calibrate_stock_decision

ROLES = ('fundamentals','technical','news','sentiment','bull','bear','risk_aggressive','risk_neutral','risk_conservative')
REVIEW_TOOL = 'review_research_decision'


def exact(value, keys):
    if not isinstance(value,dict) or set(value)!=set(keys):raise Invalid('研究建议字段缺失或包含未允许字段')


def signal(value):
    exact(value,('action','risk_score','confidence','target_price','reasoning'))
    if value['action'] not in ('买入','持有','卖出','观望','无法判断'):raise Invalid('研究建议方向无效')
    for field,maximum in [('risk_score',1),('confidence',1),('target_price',1e12)]:
        v=value[field]
        if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=maximum):raise Invalid('建议数值无效：'+field)
        if field=='target_price' and v==0:raise Invalid('目标价须为正数或未知')
    text(value['reasoning'],'研究依据',4000)
    return copy.deepcopy(value)


class ResearchReview:
    def __init__(self,repo,confirmations,investment):
        self.repo,self.confirmations,self.investment=repo,confirmations,investment

    def _evidence(self,db,principal,session,eid,entity):
        text(eid,'证据编号',200)
        row=db.execute('SELECT tool_id,request,result FROM research_tool_calls WHERE id=? AND principal=? AND session=?',
                       (eid,principal,session)).fetchone()
        if not row or not row['result']:raise Invalid('引用证据不存在、未完成或不属于当前对话')
        if row['tool_id']==REVIEW_TOOL:raise Invalid('研究建议自身不能当作事实来源证据')
        result=json.loads(row['result'])
        if result.get('status')!='ok' or result.get('stale'):raise Invalid('引用证据不可用或已陈旧')
        args=json.loads(row['request'])
        cid=args.get('confirmation_id')
        confirmed=db.execute('SELECT payload FROM entity_confirmations WHERE id=? AND principal=? AND session=?',
                             (cid,principal,session)).fetchone() if cid else None
        if not confirmed:raise Invalid('引用证据未绑定已确认研究对象')
        saved=json.loads(confirmed['payload'])
        subject=saved.get('execution_entity_id',saved['entity_id'])
        # 公司与其同码 A 股可共同用于研究；基金、指数等不同类型不可混入。
        expected=entity.rsplit(':',1)[-1]
        if not subject.startswith(('SEC:CN:A:','CO:CN:A:')) or subject.rsplit(':',1)[-1]!=expected:
            raise Invalid('引用证据的研究主体不一致')
        origin=result.get('source')
        origin=(origin if isinstance(origin,str) else canonical(origin))[:500] if origin is not None else None
        return {'evidence_id':eid,'sha256':digest(result),'source':origin,
                'observed_at':result.get('observed_at') or result.get('fetched_at')}

    def run(self,principal,session,call_id,arguments):
        text(session,'会话',200);text(call_id,'调用编号',200)
        exact(arguments,('confirmation_id','signal','perspectives'))
        original=signal(arguments['signal'])
        roles=arguments['perspectives']
        if not isinstance(roles,list) or len(roles)>len(ROLES):raise Invalid('研究视角格式无效')
        seen=set()
        for item in roles:
            exact(item,('role','summary','evidence_ids'))
            role=item['role']
            if not isinstance(role,str) or role not in ROLES or role in seen:raise Invalid('研究视角未知或重复')
            seen.add(role);text(item['summary'],'视角论点',2000)
            ids=item['evidence_ids']
            if not isinstance(ids,list) or len(ids)>10 or any(not isinstance(v,str) for v in ids) or len(set(ids))!=len(ids):raise Invalid('引用证据列表无效')
        key=digest([principal,session,call_id,REVIEW_TOOL]);fingerprint=digest(arguments)
        with self.repo.connection(True) as db:
            prior=db.execute('SELECT fingerprint,result FROM research_tool_calls WHERE id=?',(key,)).fetchone()
            if prior:
                if prior['fingerprint']!=fingerprint:raise Conflict('同一研究审查调用不能改变参数')
                return json.loads(prior['result']) if prior['result'] else {'status':'unavailable','review_id':key,'error':'原调用结果未确认，请回查历史，不自动重放'}
            if db.execute('SELECT count(*) FROM research_tool_calls WHERE principal=? AND session=? AND created_at>?',
                          (principal,session,self.repo.clock()-60)).fetchone()[0]>=20:
                raise Invalid('本对话每分钟最多执行20次研究工具，请稍后再试')
            cid=arguments['confirmation_id']
            text(cid,'确认回执',200)
            current=next((c for c in self.confirmations.current(principal,session) if c['confirmation_id']==cid),None)
            if not current:raise Invalid('需要本对话当前有效的证券确认')
            self.confirmations.validate(principal,session,cid,current['entity_id'])
            entity=current.get('execution_entity_id',current['entity_id'])
            if not entity.startswith('SEC:CN:A:'):raise Invalid('当前画像校准仅支持已确认沪深 A 股')
            ids=sorted({eid for role in roles for eid in role['evidence_ids']})
            if len(ids)>20:raise Invalid('一次研究审查最多引用20条证据')
            refs=[self._evidence(db,principal,session,eid,entity) for eid in ids]
            facts=self.investment.read(principal)
            profile=facts.get('risk_profile')
            effective=None;calibrated=False;note=None
            if not profile or original['risk_score'] is None or original['action']=='无法判断' or not refs:
                guard='unknown'
                note='风险画像、风险分、明确建议或主体证据不足，无法完成画像校准；保留原分析，不生成默认持有建议。'
            else:
                effective,calibrated,note=calibrate_stock_decision(copy.deepcopy(original),profile['profile'])
                guard='calibrated' if calibrated else 'unchanged'
            missing=[r for r in ROLES if r not in seen]
            unverified=[r['role'] for r in roles if not r['evidence_ids']]
            result={'status':'ok','review_id':key,'entity_id':entity,'name':current['label'],
                'recorded_at':datetime.fromtimestamp(self.repo.clock(),timezone.utc).isoformat(),
                'investment_fact_version':facts['version'],'risk_profile':copy.deepcopy(profile),
                'guard_policy':'legacy-risk-v1','guard_status':guard,'calibrated':calibrated,'guard_note':note,
                'original_signal':original,'effective_signal':effective,'perspectives':copy.deepcopy(roles),
                'coverage':{'status':'complete' if not missing and not unverified else 'incomplete','missing_roles':missing,'unverified_roles':unverified},
                'evidence_ids':ids,'evidence_refs':refs,
                'notice':'研究方向和风险分由 DSH 分析提出；程序只校准画像规则并保存来源，不证明分析正确。没有创建委托、提醒、持仓变更或交易。'}
            db.execute('INSERT INTO research_tool_calls VALUES(?,?,?,?,?,?,?,?,?)',
                       (key,principal,session,call_id,REVIEW_TOOL,fingerprint,canonical(arguments),canonical(result),self.repo.clock()))
            return result

    def history(self,principal,arguments):
        if not isinstance(arguments,dict) or set(arguments)-{'limit'}:raise Invalid('研究建议查询字段无效')
        limit=arguments.get('limit',20)
        if type(limit) is not int or not 1<=limit<=50:raise Invalid('最多读取50条研究建议')
        with self.repo.connection() as db:
            rows=db.execute('SELECT result FROM research_tool_calls WHERE principal=? AND tool_id=? AND result IS NOT NULL ORDER BY created_at DESC,id DESC LIMIT ?',
                            (principal,REVIEW_TOOL,limit)).fetchall()
        return {'items':[json.loads(row['result']) for row in rows],'limit':limit,'complete_history':False}
