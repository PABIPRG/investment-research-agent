"""旧数据文件的格式与完整性边界；只收有界 JSON，不读取路径或附件。"""
import json
import math
import re
from copy import deepcopy
from ..contracts import Invalid, canonical
from ..execution import digest

MAX_BYTES = 20 * 1024 * 1024
MAX_ITEMS = 100000
COLLECTIONS = {
 'strategies': {'strategies','strategy_backtests','shadows','shadow_equity','shadow_tasks','shadow_task_results','evolution_previews','gene_archive','events_ledger'},
 'holdings': {'holdings','trades','position_risk_config','position_risk_runtime'},
 'watchlist': {'watchlist'},
 'research': {'backtests','decisions','reports','briefs','research_chat_contexts'},
 'preferences': {'preferences','behavior'},
 'notifications': {'notification_center'},
}
EXCLUDED = {'preferences','notifications'}
SECRET_KEY = re.compile(r'(?:api[_-]?key|secret|password|authorization|credential|access[_-]?token|refresh[_-]?token|cookie|webhook|notification[_-]?token)',re.I)
SECRET_TEXT = re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._~+/-]{12,})',re.I)
RUNTIME_COLLECTIONS = {'shadow_tasks','shadow_task_results','position_risk_runtime'}


def pairs(items):
    result = {}
    for key, value in items:
        if key in result: raise Invalid('JSON 含重复字段，无法确定导入内容')
        result[key] = value
    return result


def bounded(value, depth=0, counter=None):
    counter = counter if counter is not None else [0]
    counter[0] += 1
    if depth > 32 or counter[0] > MAX_ITEMS: raise Invalid('数据包嵌套或记录数量超出限制')
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key,str) or len(key)>1000: raise Invalid('数据包字段无效')
            bounded(child,depth+1,counter)
    elif isinstance(value,list):
        for child in value: bounded(child,depth+1,counter)
    elif isinstance(value,str):
        if len(value)>2*1024*1024: raise Invalid('单项文字过长')
    elif isinstance(value,float) and not math.isfinite(value): raise Invalid('数据包数值必须有限')


def sanitize(value, counts):
    if isinstance(value,dict):
        result = {}
        for key, child in value.items():
            if SECRET_KEY.search(key) or key in ('preview_token','lease_token','session_token','request_headers'):
                counts[0] += 1
            else: result[key] = sanitize(child,counts)
        return result
    if isinstance(value,list): return [sanitize(x,counts) for x in value]
    if isinstance(value,str):
        result, number = SECRET_TEXT.subn('[凭据已排除]',value)
        counts[0] += number
        return result
    return value


def check_hash(value, actual, label):
    if not isinstance(value,dict) or value.get('algorithm')!='sha256' or value.get('value')!=actual:
        raise Invalid(label+'完整性校验失败')


def trading(snapshot):
    if snapshot.get('backend')!='trading-core' or type(snapshot.get('schemaVersion')) is not int or snapshot['schemaVersion'] not in (1,2,3,4):
        raise Invalid('仅支持 trading-core schema 1–4')
    categories = snapshot.get('categories')
    if not isinstance(categories,dict) or not categories or set(categories)-set(COLLECTIONS): raise Invalid('旧数据分类无效')
    result = {}
    for category, payload in categories.items():
        if not isinstance(payload,dict) or not isinstance(payload.get('collections'),dict): raise Invalid('旧分类缺少 collections')
        entries = payload['collections']
        allowed = set(COLLECTIONS[category])
        if snapshot['schemaVersion']==1:
            allowed -= {'trades','evolution_previews','gene_archive','events_ledger'}
        if snapshot['schemaVersion']<3 and category=='notifications': raise Invalid('此版本没有通知分类')
        if snapshot['schemaVersion']<4: allowed -= {'position_risk_config','position_risk_runtime'}
        if set(entries)-allowed or not all(isinstance(v,dict) for v in entries.values()): raise Invalid('旧集合超出当前版本契约')
        result[category] = deepcopy(entries)
    if snapshot.get('revision') is not None and snapshot['revision'] != digest(result): raise Invalid('旧数据快照摘要不匹配')
    return result


def decode(content):
    if not isinstance(content,str) or len(content.encode('utf-8')) > MAX_BYTES: raise Invalid('请上传不超过 20 MiB 的 JSON 数据包')
    try: raw=json.loads(content,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Invalid('非有限数值')))
    except (ValueError,RecursionError): raise Invalid('文件不是有效的 JSON 数据包') from None
    bounded(raw)
    if not isinstance(raw,dict): raise Invalid('数据包必须是 JSON 对象')
    original_digest=digest(raw)
    domains={};warnings=[];attachments=[]
    if raw.get('backend')=='trading-core': domains['trading-core']=raw
    elif raw.get('format')=='pa-product-data-package':
        if type(raw.get('formatVersion')) is not int or raw['formatVersion']!=1: raise Invalid('不支持的产品包版本')
        check_hash(raw.get('integrity'),digest({k:v for k,v in raw.items() if k!='integrity'}),'产品包')
        scope=raw.get('exportScope');records=raw.get('domains')
        if not isinstance(scope,dict) or not scope.get('domains') or not isinstance(scope.get('domains'),list) or not all(isinstance(x,str) for x in scope['domains']) or len(set(scope['domains']))!=len(scope['domains']): raise Invalid('产品包领域范围无效')
        if not isinstance(records,dict) or set(records)-set(scope['domains']): raise Invalid('产品包领域超出声明范围')
        missing=raw.get('missing',[])
        if not isinstance(missing,list) or any(not isinstance(x,dict) or x.get('domain') not in scope['domains'] for x in missing): raise Invalid('缺失领域声明无效')
        missing_names={x['domain'] for x in missing}
        if len(missing_names)!=len(missing) or set(records)&missing_names or set(records)|missing_names!=set(scope['domains']) or type(raw.get('complete')) is not bool or raw['complete']!=(not missing): raise Invalid('产品包缺失声明与内容不一致')
        for name,item in records.items():
            if not isinstance(item,dict) or not isinstance(item.get('payload'),dict): raise Invalid('产品包领域内容无效')
            check_hash(item.get('checksum'),digest(item['payload']),name)
            version=str(item.get('schemaVersion',''))
            expected=item['payload'].get('schemaVersion') if name=='trading-core' else item['payload'].get('schema_version')
            if not version or name in ('trading-core','research-partner') and version!=str(expected): raise Invalid('领域清单版本与内容不一致')
            if name not in ('trading-core','research-partner'):
                warnings.append('未迁移的领域：'+name)
                continue
            domains[name]=item['payload']
        attachments=raw.get('attachments',[])
        if not isinstance(attachments,list): raise Invalid('附件声明无效')
        for item in attachments:
            if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not re.fullmatch(r'[^/\\\x00]{1,255}',item['name']): raise Invalid('附件名无效')
        if len({x['name'] for x in attachments})!=len(attachments) or sorted(x['name'] for x in attachments)!=scope.get('attachments',[]): raise Invalid('附件声明与范围不一致')
        if attachments: warnings.append('附件仅记录缺失清单，本入口不读取本地路径或还原附件')
        warnings += ['来源包缺少领域：'+x['domain'] for x in missing]
    else: raise Invalid('仅支持旧 trading-core 快照或产品数据包 format 1')
    if not domains: raise Invalid('数据包没有可迁移领域')
    counts=[0];normalized={'source_digest':original_digest,'trading':{},'mandates':None,'attachments':attachments}
    if 'trading-core' in domains:
        categories=trading(domains['trading-core'])
        for category, collections in categories.items():
            if category in EXCLUDED:
                warnings.append('不会恢复旧'+('通知及投递授权' if category=='notifications' else '偏好/模型配置与行为状态'))
                continue
            normalized['trading'][category]=sanitize({k:v for k,v in collections.items() if k not in RUNTIME_COLLECTIONS},counts)
            for name in set(collections)&RUNTIME_COLLECTIONS: warnings.append('不会恢复运行态集合：'+name)
    if 'research-partner' in domains:
        snapshot=domains['research-partner']
        check_hash(snapshot.get('integrity'),digest(snapshot.get('mandates')),'委托包')
        if snapshot.get('format')!='research-partner-data-package' or snapshot.get('domain')!='research-partner' or type(snapshot.get('format_version')) is not int or snapshot.get('format_version')!=1 or not str(snapshot.get('schema_version','')).startswith('1.'):
            raise Invalid('不支持的委托包格式')
        normalized['mandates']=sanitize(snapshot.get('mandates'),counts)
    if counts[0]: warnings.append(f'已排除 {counts[0]} 处凭据字段或凭据文本')
    normalized['warnings']=warnings
    return normalized
