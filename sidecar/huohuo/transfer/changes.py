"""供人核对的逐项变化；不把全部领域原始 JSON 塞进确认提示。"""
from ..contracts import Invalid


def changes(before,plan):
    output=[]
    for collection,category,fields in (('default','holdings',('quantity','cost_price')),('watchlist','watchlist',('reason',))):
        previous={x['ticker']:x for x in before[collection]}
        for item in plan['facts'][collection]:
            old=previous.get(item['ticker'])
            if item==old: continue
            output.append({'category':category,'kind':'新增' if old is None else '更新','name':item['name'],'code':item['ticker'],
                'before':{k:old.get(k) for k in fields} if old else None,'after':{k:item.get(k) for k in fields}})
    known={x['request_id'] for x in before['manual_trades']}
    for item in plan['facts']['manual_trades']:
        if item['request_id'] not in known:
            output.append({'category':'holdings','kind':'补记历史成交','name':item['name'],'code':item['ticker'],'before':None,
                'after':{key:item[key] for key in ('side','quantity','price','fees','traded_at','affects_holdings')}})
    for item in plan['strategies']:
        output.append({'category':'strategies','kind':'待重新验证候选','name':item['name'],'before':None,
            'after':{key:item[key] for key in ('kind','params','symbols','rationale','status')}})
    for item in plan['mandates']:
        revision=next(x for x in item['revisions'] if x['revision']==item['mandate']['current_revision'])
        output.append({'category':'mandates','kind':'暂停迁入','name':revision['goal'],'before':None,
            'after':{'scope':revision['scope'],'status':item['mandate']['status'],'external_contact_authorized':False}})
    return output


def page(items,category,offset,limit):
    if type(offset) is not int or not 0<=offset<=50000 or type(limit) is not int or not 1<=limit<=100: raise Invalid('预览分页范围无效')
    if category not in (None,'holdings','watchlist','strategies','research','mandates'): raise Invalid('预览分类无效')
    selected=[x for x in items if category is None or x['category']==category]
    return {'items':selected[offset:offset+limit],'offset':offset,'total':len(selected),'limit':limit}
