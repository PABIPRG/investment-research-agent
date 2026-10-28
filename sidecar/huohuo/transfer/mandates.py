"""迁入委托保持暂停，旧日程/依赖禁用，旧联系许可不具备执行效力。"""
from datetime import datetime
from ..contracts import Invalid, scope as validate_scope
from ..execution import digest
from ..research_partner.models import Mandate, MandateRevision, MandateSubject, MandateRequirement, TrackingDependency, MandateSchedule


def validated(model,value,label):
    try: return model.model_validate(value)
    except (ValueError,TypeError): raise Invalid(label+'不符合正式委托结构') from None


def map_mandates(entries,store,principal,instance,at):
    if not isinstance(entries,list) or len(entries)>1000: raise Invalid('委托包须为最多 1000 项的列表')
    result=[];seen=set();skipped=0;conflicts=[]
    for entry in entries:
        if not isinstance(entry,dict): raise Invalid('委托条目必须是对象')
        old=validated(Mandate,entry.get('mandate'),'委托')
        if old.mandate_id in seen: raise Invalid('委托包重复包含相同标识')
        seen.add(old.mandate_id)
        target='MND_'+digest([principal,'legacy',old.mandate_id])[:32]
        revisions=entry.get('revisions')
        if not isinstance(revisions,list) or not revisions: raise Invalid('旧委托缺少修订链')
        output={'mandate':old.model_copy(update={'mandate_id':target,'principal_id':principal,'instance_id':instance,'status':'ended' if old.status=='ended' else 'paused','source_session_id':None,'source_message_ref':None}).model_dump(mode='json'),
                'revisions':[],'subjects':[],'requirements':[],'dependencies':[],'schedules':[],'source_id':old.mandate_id}
        for value in revisions:
            if not isinstance(value,dict): raise Invalid('旧修订格式无效')
            revision=validated(MandateRevision,value.get('revision'),'修订')
            if revision.mandate_id!=old.mandate_id: raise Invalid('旧修订引用了其他委托')
            try: validate_scope(revision.scope)
            except Invalid as exc: raise Invalid('旧委托研究范围不能直接迁入，请取消选择委托分类并保留原始导出：'+str(exc)) from None
            output['revisions'].append(revision.model_copy(update={'mandate_id':target,'triggers':[],
                'contact_policy':{'channels':[],'max_retries':0},'basis':{'legacy_import':{'source_id':old.mandate_id,'requires_review':True}},'created_by':'legacy_import'}).model_dump(mode='json'))
            for key,model,idfield,prefix in (('subjects',MandateSubject,None,None),('requirements',MandateRequirement,'requirement_id','REQ_'),('dependencies',TrackingDependency,'dependency_id','legacy-dependency-')):
                items=value.get(key,[])
                if not isinstance(items,list) or len(items)>1000: raise Invalid('旧委托关联条目无效')
                for item in items:
                    parsed=validated(model,item,key)
                    if parsed.mandate_id!=old.mandate_id or parsed.revision!=revision.revision: raise Invalid('旧委托关联条目引用错误')
                    update={'mandate_id':target}
                    if idfield: update[idfield]=prefix+digest([target,getattr(parsed,idfield)])[:32]
                    if key=='dependencies': update['active']=False
                    output[key].append(parsed.model_copy(update=update).model_dump(mode='json'))
        numbers=sorted(x['revision'] for x in output['revisions'])
        if numbers!=list(range(1,old.current_revision+1)): raise Invalid('旧委托修订链不连续')
        schedules=entry.get('schedules',[])
        if not isinstance(schedules,list) or len(schedules)>1000: raise Invalid('旧日程列表无效')
        for value in schedules:
            schedule=validated(MandateSchedule,value,'日程')
            if schedule.mandate_id!=old.mandate_id or schedule.revision>old.current_revision: raise Invalid('旧日程引用错误')
            output['schedules'].append(schedule.model_copy(update={'mandate_id':target,'schedule_id':'SCH_'+digest([target,schedule.schedule_id])[:32],'enabled':False,'last_instance_key':None}).model_dump(mode='json'))
        for key,fields in (('subjects',('revision','entity_id','role')),('requirements',('requirement_id',)),('dependencies',('dependency_id',)),('schedules',('schedule_id',))):
            identities=[tuple(x[field] for field in fields) for x in output[key]]
            if len(identities)!=len(set(identities)): raise Invalid('旧委托包含重复关联记录')
        output['requirements'].append(MandateRequirement(requirement_id='REQ_'+digest([target,'review'])[:32],mandate_id=target,revision=old.current_revision,code='legacy_import_review',
            detail='这是迁入的旧委托。请先修改并重新确认当前研究范围与联系约定，再恢复跟进；旧授权不生效。',created_at=datetime.fromisoformat(at)).model_dump(mode='json'))
        existing=store.get_mandate_internal(target)
        if existing:
            if existing.principal_id!=principal: raise Invalid('导入目标委托身份冲突')
            skipped+=1;conflicts.append({'source_id':old.mandate_id,'target_id':target,'reason':'已有迁入版本，保留当前正式委托；旧修订另存只读档案'})
            continue
        result.append(output)
    return result,{'incoming':len(entries),'added':len(result),'skipped':skipped,'conflicts':conflicts}


def write_mandates(store,items):
    for item in items:
        store.import_mandate(Mandate.model_validate(item['mandate']),[MandateRevision.model_validate(x) for x in item['revisions']],
            subjects=[MandateSubject.model_validate(x) for x in item['subjects']],requirements=[MandateRequirement.model_validate(x) for x in item['requirements']],
            dependencies=[TrackingDependency.model_validate(x) for x in item['dependencies']],schedules=[MandateSchedule.model_validate(x) for x in item['schedules']])
        store._connect().execute('INSERT INTO mandate_generation VALUES (?,0)',(item['mandate']['mandate_id'],))
