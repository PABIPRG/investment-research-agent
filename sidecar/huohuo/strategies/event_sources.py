"""独立策略新闻采集范围；复用注入来源，不依赖持续委托存在。"""
from ..contracts import Invalid

MAX_SECURITIES = 20


def scope(docs, policy):
    securities = {}
    for sid in policy['strategy_ids']:
        for value in (docs.get('strategies', sid) or {}).get('securities', []):
            securities.setdefault(value['code'], value)
    if len(securities) > MAX_SECURITIES:
        raise Invalid(f'事件研究每份计划最多覆盖 {MAX_SECURITIES} 只证券，请缩小范围或关闭事件候选')
    return [securities[code] for code in sorted(securities)]


def collect(service, securities):
    if service.event_source is None:
        raise Invalid('策略新闻来源尚未装配，未将来源缺失当作无新闻')
    if not securities or len(securities) > MAX_SECURITIES:
        raise Invalid('策略新闻采集范围为空或超出上限')
    try:
        events = service.event_source([dict(s) for s in securities])
    except Exception as exc:
        raise Invalid('策略新闻来源读取失败，本次未生成候选；保留旧记录') from exc
    if not isinstance(events, list) or len(events) > 100:
        raise Invalid('策略新闻来源返回无效或超过 100 条，本次未生成候选')
    allowed = {s['code'] for s in securities}
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get('securities'), list):
            raise Invalid('策略新闻来源缺少证券绑定')
        if any(not isinstance(s, dict) or s.get('code') not in allowed for s in event['securities']):
            raise Invalid('策略新闻来源返回授权范围之外的证券，未生成候选')
    return events
