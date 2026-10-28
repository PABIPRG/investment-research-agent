"""按所选分类生成可审阅的确定性计划；部分非法会阻止整批提交。"""
import json
from ..contracts import Invalid, canonical
from ..execution import digest
from ..investment.service import Investment
from .facts import map_facts
from .strategies import map_strategies
from .mandates import map_mandates
from .changes import changes

CATEGORIES={'holdings':'持仓与历史成交','watchlist':'自选','strategies':'策略候选与旧验证档案','research':'旧研究与对话档案','mandates':'持续委托（暂停）'}


def available(package):
    result=[key for key in CATEGORIES if key in package['trading'] or key=='mandates' and package['mandates'] is not None]
    return [{'id':key,'label':CATEGORIES[key]} for key in result]


def state_version(store,principal):
    db=store._connect()
    facts=db.execute('SELECT version FROM investment_facts WHERE principal=?',(principal,)).fetchone()
    strategies=[dict(x) for x in db.execute('SELECT collection,id,document FROM strategy_documents WHERE principal=? ORDER BY collection,id',(principal,))]
    mandates=[dict(x) for x in db.execute('SELECT mandate_id,current_revision,status,updated_at FROM mandates WHERE principal_id=? ORDER BY mandate_id',(principal,))]
    return digest({'facts':facts['version'] if facts else 0,'strategies':strategies,'mandates':mandates})


def archive_rows(package,selected):
    output=[]
    for category in selected:
        if category=='mandates':
            for entry in package['mandates']:
                mid=entry['mandate']['mandate_id']
                output.append({'category':'mandates','source_id':mid,'title':'旧委托修订与约定','document':entry})
            continue
        for collection,records in package['trading'].get(category,{}).items():
            if collection in ('holdings','trades','watchlist'):
                output.append({'category':category,'source_id':collection,'title':'旧'+CATEGORIES[category]+'原始记录','document':records})
            else:
                for key,value in records.items():
                    if isinstance(value,dict) and value.get('status') in ('pending','running','queued'):
                        continue
                    title=value.get('title') or value.get('name') or value.get('question') if isinstance(value,dict) else None
                    label={'reports':'研究报告','decisions':'判断记录','briefs':'研究简报','research_chat_contexts':'对话上下文','backtests':'历史回测','strategy_backtests':'策略回测','shadows':'影子验证','shadow_equity':'历史影子净值','evolution_previews':'历史演进审计','gene_archive':'历史基因档案','events_ledger':'策略事件记录','strategies':'原策略定义'}.get(collection,'旧资料')
                    output.append({'category':category,'source_id':collection+':'+key,'title':str(title or label+' · '+key)[:200],'document':value})
    if len(output)>10000: raise Invalid('只读档案超过 10000 条上限')
    return output


def build_plan(service,principal,package,selected,rules,at):
    allowed={x['id'] for x in available(package)}
    if not isinstance(selected,list) or not selected or not all(isinstance(x,str) for x in selected) or len(selected)!=len(set(selected)) or set(selected)-allowed:
        raise Invalid('请选择数据包实际包含的分类')
    if not isinstance(rules,dict) or set(rules)-set(selected) or any(value not in ('keep_local','use_import') for value in rules.values()):
        raise Invalid('冲突规则须为保留当前或使用导入值')
    if rules.get('mandates','keep_local')!='keep_local': raise Invalid('现有委托必须保留；旧修订可从迁移档案回看')
    resolved={category:rules.get(category,'keep_local') for category in selected}
    version,current,_=Investment(service.store)._load(principal)
    existing={row['id']:json.loads(row['document']) for row in service.store._connect().execute("SELECT id,document FROM strategy_documents WHERE principal=? AND collection='strategies'",(principal,))}
    plan={'selected':selected,'rules':resolved,'fact_version':version,'facts':current,'strategies':[],'mandates':[],'archives':[],
          'summary':{},'warnings':list(package['warnings']),'blockers':[]}
    try:
        plan['facts'],summary,warnings=map_facts(current,package['trading'],selected,resolved,service.resolve_name,at)
        plan['summary'].update(summary);plan['warnings'].extend(warnings)
    except (Invalid,KeyError,TypeError,ValueError) as exc: plan['blockers'].append({'category':'holdings/watchlist','message':str(exc)[:500]})
    if 'strategies' in selected:
        try:
            plan['strategies'],plan['summary']['strategies']=map_strategies(package['trading'],existing,resolved['strategies'],service.resolve_name,at)
            plan['warnings'].append('旧策略重新成为待验证候选；旧回测、影子与收益仅归档，不作为新实例验证结果')
        except (Invalid,KeyError,TypeError,ValueError) as exc: plan['blockers'].append({'category':'strategies','message':str(exc)[:500]})
    if 'mandates' in selected:
        try:
            plan['mandates'],plan['summary']['mandates']=map_mandates(package['mandates'],service.store,principal,service.instance_id,at)
            plan['warnings'].append('旧委托保持暂停或结束；需要先修改并确认研究范围及联系约定，日程与旧授权不会恢复')
        except (Invalid,KeyError,TypeError,ValueError) as exc: plan['blockers'].append({'category':'mandates','message':str(exc)[:500]})
    if not plan['blockers']:
        plan['archives']=archive_rows(package,selected)
        if 'research' in selected: plan['summary']['research']={'incoming':sum(x['category']=='research' for x in plan['archives'])}
        plan['summary']['archives']={'incoming':len(plan['archives']),'label':'只读旧资料，不是 DSH 历史会话或新研究证据'}
    plan['changes']=changes(current,plan) if not plan['blockers'] else []
    return plan
