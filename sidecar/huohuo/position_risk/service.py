"""风险配置投影到同一委托核心；只保存绑定，不拥有第二个调度或投递台账。"""
from datetime import datetime,timezone
from ..contracts import Invalid
from ..execution import digest
from ..research_partner.commands import MandateCreateRequest,MandateStatusRequest
from ..research_partner.contact_rules import compile_rule
from ..research_partner.sources import trigger
from .configuration import document,selected,status,scope
from .legacy import TARGET_KINDS,_resolved_price,suggestion_for_profile
from .repository import Bindings

def key_for(settings,code,kind):
    source,config=selected(settings,code)
    return digest([source,config,settings['rearms'].get(code+':'+kind,0)])

class PositionRisk:
    def __init__(self,core):
        self.core,self.store=core,core.store
        self.bindings=Bindings(self.store)
        self.store.position_risk=self
    def at(self):return datetime.fromtimestamp(self.core.repo.clock(),timezone.utc)
    def refresh(self):
        for principal in self.bindings.principals():
            _,facts,_=self.core.investment._load(principal)
            self.reconcile(principal,facts)
    def _close(self,row):
        mandate=self.store.get_mandate_internal(row['mandate_id'])
        if mandate and mandate.status!='ended':
            self.core.service.end(self.core.context(row['principal']),row['mandate_id'],MandateStatusRequest(
                expected_revision=mandate.current_revision,idempotency_key='position:end:'+digest([row['mandate_id'],mandate.current_revision])))
            self.core.invalidate(row['mandate_id'])
        self.bindings.deactivate(row['principal'],row['ticker'],row['kind'])
    def reconcile(self,principal,facts):
        settings=document(facts)
        holdings={x['ticker']:x for x in facts['default'] if x['quantity']>0}
        existing={(r['ticker'],r['kind']):r for r in self.bindings.all(principal)}
        for code in sorted(set(holdings)|{r['ticker'] for r in existing.values()}):
            source,config=selected(settings,code);holding=holdings.get(code)
            active=status(config,self.at()) in ('active','scheduled') and holding is not None and holding['cost_price'] is not None and holding['cost_price']>0
            for kind in TARGET_KINDS:
                old=existing.get((code,kind))
                wanted=active and config[kind]['enabled']
                if not wanted:
                    if old and old['alive']:self._close(old)
                    continue
                config_key=key_for(settings,code,kind)
                # 成本变化保持激活快照；明确重新布防/改设置才创建新代次。
                if old and old['alive'] and old['config_key']==config_key:continue
                if old and old['alive']:self._close(old)
                basis_cost=holding['cost_price']
                try:price=_resolved_price(kind,config[kind],basis_cost)
                except ValueError:continue  # 无效旧目标不能阻止修正正式持仓事实。
                generation=(old['generation'] if old else 0)+1
                sc=scope(code)
                rule={'mode':'condition','notify_on':'first_entry','cooldown_minutes':0,
                      'condition':{'type':'numeric','metric':'price','operator':'>=' if kind=='take_profit' else '<=','threshold':price}}
                policy=compile_rule(rule,sc,['app'])
                marker={'ticker':code,'name':holding.get('name'),'kind':kind,'config_key':config_key,'basis_cost':basis_cost,
                        'resolved_price':price,'generation':generation,'method_version':'position-risk-v1'}
                label='止盈' if kind=='take_profit' else '止损'
                view=self.core.service.create(self.core.context(principal),MandateCreateRequest(
                    goal=f"{holding.get('name') or code}（{code}）持仓{label}：价格{'达到' if kind=='take_profit' else '低于或等于'} {price} 元时应用内联系一次",
                    scope=sc,subjects=[{'entity_id':sc['entity_id']}],triggers=trigger(sc,policy),contact_policy=policy,
                    basis={'position_risk':marker,'contact_rule':rule,'contact_note':'用户明确确认的持仓风险配置；仅应用内联系，不交易',
                           'fact_version':self.core.investment._load(principal)[0],'entity_source':'confirmed_investment_holding'},
                    idempotency_key='position:create:'+digest([principal,code,kind,config_key,generation])))
                mid=view['mandate']['mandate_id']
                self.store._connect().execute('INSERT INTO mandate_generation VALUES(?,0)',(mid,))
                self.bindings.put({'principal':principal,'ticker':code,'kind':kind,'config_key':config_key,'mandate_id':mid,
                    'basis_cost':basis_cost,'resolved_price':price,'generation':generation,'alive':1})
                self.core.sources.catch_up(principal,mid)
    def reason(self,mid,exclude_decision=None):
        row=self.bindings.for_mandate(mid)
        if not row:return None
        if not row['alive']:return 'position_plan_inactive'
        mandate=self.store.get_mandate_internal(mid)
        if not mandate or mandate.status!='tracking':return 'position_mandate_not_tracking'
        revision=self.store.get_revision(mid,mandate.current_revision)
        if mandate.current_revision!=1 or not revision or revision.basis.get('position_risk',{}).get('config_key')!=row['config_key']:
            return 'position_plan_modified'
        _,facts,_=self.core.investment._load(row['principal']);settings=document(facts)
        holding=next((x for x in facts['default'] if x['ticker']==row['ticker'] and x['quantity']>0),None)
        if not holding:return 'position_holding_missing'
        if holding['cost_price'] is None or holding['cost_price']<=0:return 'position_cost_unknown'
        _,config=selected(settings,row['ticker'])
        state=status(config,self.at())
        if state!='active':return 'position_config_'+state
        if key_for(settings,row['ticker'],row['kind'])!=row['config_key']:return 'position_config_changed'
        if self.bindings.consumed(mid,exclude_decision):return 'position_target_consumed'
        return None
    def view(self,principal,facts=None):
        if facts is None:_,facts,_=self.core.investment._load(principal)
        settings=document(facts);rows={(r['ticker'],r['kind']):r for r in self.bindings.all(principal)}
        plans=[]
        for holding in facts['default']:
            code=holding['ticker'];source,config=selected(settings,code);state=status(config,self.at());targets={};changed=False;errors=[]
            if state in ('active','scheduled') and (holding['cost_price'] is None or holding['cost_price']<=0):state='cost_unknown'
            for kind in TARGET_KINDS:
                row=rows.get((code,kind))
                if not row or not row['alive']:
                    if state in ('active','scheduled') and config[kind]['enabled']:
                        try:_resolved_price(kind,config[kind],holding['cost_price'])
                        except ValueError:errors.append('绝对目标价与当前成本方向不符，请修改单仓配置')
                    continue
                m=self.store.get_mandate_internal(row['mandate_id'])
                consumed=self.bindings.consumed(row['mandate_id'])
                target_status='triggered' if consumed else m.status if m and m.status!='tracking' else state
                if m and m.current_revision!=1:target_status='modified'
                targets[kind]={**{k:row[k] for k in ('basis_cost','resolved_price','generation','mandate_id')},'status':target_status}
                changed=changed or row['basis_cost']!=holding['cost_price']
            plans.append({'ticker':code,'name':holding.get('name'),'source':source,'status':'invalid_target' if errors else state,'errors':errors,'basis_changed':changed,'targets':targets})
        profile=facts.get('risk_profile')
        return {'config':settings,'global_status':status(settings['global'],self.at()),'plans':plans,'suggestion':suggestion_for_profile(profile['profile']) if profile else None,
                'notice':'激活时成本冻结；成本变化需重新布防。每个目标代次只联系一次，使用正式委托的任务、证据、取消与通知资格；不下单。'}
    def effects(self,principal,before,after):
        previous={x['ticker']:x for x in before['default']};current={x['ticker']:x for x in after['default']}
        settings=document(after);bindings=self.bindings.all(principal);effects=[]
        for code in sorted(set(previous)|set(current)):
            old,new=previous.get(code),current.get(code)
            if old==new:continue
            active=[r for r in bindings if r['ticker']==code and r['alive']]
            _,config=selected(settings,code)
            if not new or new['quantity']<=0 or new['cost_price'] is None or new['cost_price']<=0:
                if active:effects.append(f'{code}：平仓或成本未知将撤销已有持仓风险委托资格。')
            elif active:
                effects.append(f"{code}：沿用已确认的激活阈值（"+'、'.join(str(r['resolved_price'])+' 元' for r in active)+'），成本变化不移动阈值，也不恢复已暂停的委托。')
            elif status(config,self.at()) in ('active','scheduled'):
                for kind in TARGET_KINDS:
                    if not config[kind]['enabled']:continue
                    try:price=_resolved_price(kind,config[kind],new['cost_price'])
                    except ValueError:
                        effects.append(f'{code}：已有绝对目标价与当前成本方向不符，本目标不激活；持仓事实仍可保存。');continue
                    effects.append(f"{code}：按已确认的持仓风险约定建立{'止盈' if kind=='take_profit' else '止损'}委托；激活成本 {new['cost_price']} 元、目标 {price} 元，仅应用内联系一次。")
        return effects
    def alerts(self,principal):
        result=[]
        for decision in self.bindings.decisions(principal):
            p=decision['position_risk'];label='止盈' if p['kind']=='take_profit' else '止损'
            result.append({'id':'risk-position:'+decision['decision_id'],'source':'position_plan','severity':'中' if p['kind']=='take_profit' else '高',
                'title':p['ticker']+' '+label+'目标已触发','detail':decision['detail'] or f"激活成本 {p['basis_cost']} 元、目标 {p['resolved_price']} 元，已取得一次联系资格；实际投递请回查委托。",
                'codes':[p['ticker']],'strategy_id':None,'ts':decision['created_at'],'mandate_id':decision['mandate_id'],'position_risk':p})
        return result
