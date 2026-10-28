"""用户确认的后台范围；停止、改约和结果写入使用同一事务边界。"""
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from ..contracts import Invalid, canonical
from ..execution import Conflict
from .validation import exact, identifier

ZONE = ZoneInfo('Asia/Shanghai')
ACTIONS = {'backtest', 'shadow', 'evolve'}
DEFAULT = {'revision': 0, 'enabled': False, 'daily_time': '17:00', 'strategy_ids': [],
           'actions': ['backtest', 'shadow', 'evolve'], 'retest_days': 7,
           'lookback_days': 365, 'event_candidates': False, 'archive_recall': False}

def validate_policy(value):
    exact(value, tuple(DEFAULT))
    if type(value['revision']) is not int or value['revision'] < 0:
        raise Invalid('后台计划版本无效')
    for key in ('enabled', 'event_candidates', 'archive_recall'):
        if type(value[key]) is not bool: raise Invalid('后台计划开关无效')
    if not isinstance(value['daily_time'], str) or not re.fullmatch(r'(1[6-9]|2[0-3]):[0-5][0-9]', value['daily_time']):
        raise Invalid('后台验证时间须在北京时间 16:00–23:59 的已收盘时段')
    ids = value['strategy_ids']
    if not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
        raise Invalid('后台策略范围无效')
    for sid in ids: identifier(sid)
    actions = value['actions']
    if not isinstance(actions, list) or not actions or any(not isinstance(x, str) or x not in ACTIONS for x in actions) or len(set(actions)) != len(actions):
        raise Invalid('后台只能运行回测、影子验证和生成预案')
    for key, low, high in [('retest_days', 1, 365), ('lookback_days', 40, 1095)]:
        if type(value[key]) is not int or not low <= value[key] <= high: raise Invalid('后台验证间隔或样本天数无效')
    if value['enabled'] and not ids: raise Invalid('请选择明确授权的策略范围')
    return {**value, 'strategy_ids': sorted(ids), 'actions': sorted(actions)}

def read(service, principal):
    from ..research_partner.strategy_plans import read as core_read
    return core_read(service, principal)

def next_time(now, clock, include_today=True):
    local = datetime.fromtimestamp(now, ZONE)
    hour, minute = map(int, clock.split(':'))
    point = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not include_today or point.timestamp() <= now: point += timedelta(days=1)
    while point.weekday() >= 5: point += timedelta(days=1)
    return point.timestamp()

def prepare(service, docs, payload):
    current = read(service, docs.principal)
    if payload['revision'] != current['revision']: raise Conflict('后台计划已更新，请重新预览')
    for sid in payload['strategy_ids']: service.owned(docs, sid)
    if payload['enabled'] and payload['event_candidates']:
        from .event_sources import scope
        scope(docs,payload)
    names = '、'.join(docs.get('strategies', sid)['name'] for sid in payload['strategy_ids'])
    if not payload['enabled']: return '停止策略后台计划；取消未开始的任务，已在途结果不会写入。保留既有验证记录。'
    features = '、'.join({'backtest': '定期回测', 'shadow': '收盘后影子验证', 'evolve': '生成演进预案'}[a] for a in payload['actions'])
    return (f"启用策略后台计划：{names}；工作日北京时间 {payload['daily_time']}，{features}；"
            f"回测间隔 {payload['retest_days']} 天、样本 {payload['lookback_days']} 天。"
            + ('按上述时间独立读取所选证券新闻，最多 20 只；来源失败单独记录，再由 DSH 生成待确认候选建议。' if payload['event_candidates'] else '')
            + ('允许召回适配当前市场环境的归档建议。' if payload['archive_recall'] else '')
            + '只计算研究模拟；新候选、归档召回和预案应用均另需你确认。')

def apply(service, docs, payload):
    prepare(service, docs, payload)
    from ..research_partner.strategy_plans import apply as core_apply
    return core_apply(service, docs.principal, payload)


def assert_active(service, principal, revision):
    from ..research_partner.strategy_plans import assert_active as core_active
    return core_active(service, principal, revision)
