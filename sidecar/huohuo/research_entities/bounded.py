"""沿用旧 equity financials_lookup/profile 的 AKShare 数据入口和期间选择。

适配差异：只读执行绑定 Scope，不重解 query；第三方采集在独立短命进程，
不修改宿主代理配置。原始单位不明时保持 unknown，不推断单季/累计。
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from ..contracts import Invalid, canonical, scope as validate_scope

CAPABILITIES={'version':1,'operations':['quote_snapshot','company_profile','financial_summary'],'financial_basis':['source_abstract'],'max_records':80}

def financial_values(scope, raw):
    """摘要原值不换单位；缺失、歧义和非数值不能作为已取得的指标。"""
    rows = raw.get('records')
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise Invalid('provider_schema_invalid')
    matching = [row for row in rows if row.get('指标') == scope['metric'] and scope['period'] in row]
    if not matching:
        raise Invalid('requested_period_or_metric_not_covered')
    if len(matching) != 1:
        raise Invalid('requested_metric_ambiguous')
    value = matching[0][scope['period']]
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)) or not Decimal(str(value)).is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise Invalid('requested_value_unavailable') from None
    return {'metric': scope['metric'], 'period': scope['period'], 'basis': 'source_abstract',
            'unit': 'source_unspecified', 'records': matching}


def validate_financial_document(document, binding):
    """采集、证据接收与来源事件共用同一准入边界，不只相信外层 Scope。"""
    if document.get('scope') != binding:
        raise Invalid('financial evidence scope mismatch')
    raw = document.get('raw')
    if not isinstance(raw, dict) or raw.get('code') != binding['entity_id'].split(':')[-1]:
        raise Invalid('financial evidence subject mismatch')
    if document.get('source_hash') != hashlib.sha256(canonical(raw).encode()).hexdigest():
        raise Invalid('financial evidence source hash mismatch')
    if document.get('values') != financial_values(binding, raw):
        raise Invalid('financial evidence semantics mismatch')
    expected_url = 'https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/' + raw['code'] + '.phtml'
    if document.get('source') != 'akshare.stock_financial_abstract' or document.get('source_url') != expected_url:
        raise Invalid('financial evidence source mismatch')
    try:
        observed = datetime.fromisoformat(document.get('observed_at', ''))
        if observed.tzinfo is None:
            raise ValueError
    except (TypeError, ValueError):
        raise Invalid('financial evidence observation time missing') from None

def collect(scope, loader=None):
    scope=validate_scope(scope)
    base={'schema_version':1,'scope':scope,'observed_at':datetime.now(timezone.utc).isoformat(),'source':'akshare.stock_profile_cninfo' if scope['operation']=='company_profile' else 'akshare.stock_financial_abstract','method':scope['operation']+'_v1','limitations':['这是数据源摘要，不是公告原文；摘要未明确单位/累计或单季口径时不能据此作阈值判断。']}
    try:
        if loader is None:
            result=subprocess.run([sys.executable,'-m','huohuo.research_entities.provider'],input=canonical(scope),text=True,capture_output=True,timeout=20,check=True)
            raw=json.loads(result.stdout)
        else:raw=loader(scope)
        if not isinstance(raw,dict) or raw.get('code')!=scope['entity_id'].split(':')[-1]:
            return {**base,'status':'error','reason':'provider_subject_mismatch'}
        rows=raw.get('records')
        if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):return {**base,'status':'error','reason':'provider_schema_invalid'}
        document={**base,'source_url':('https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/'+raw['code']+'.phtml') if scope['operation']=='financial_summary' else 'https://webapi.cninfo.com.cn/','source_hash':hashlib.sha256(canonical(raw).encode()).hexdigest(),'raw':raw}
        if not rows:return {**document,'status':'empty','reason':'no_source_records'}
        if scope['operation']=='financial_summary':
            try: values=financial_values(scope,raw)
            except Invalid as exc:return {**document,'status':'unavailable','reason':str(exc)}
        else:values={'code':raw['code'],'profile':rows[:1]}
        return {**document,'status':'ok','values':values}
    except subprocess.TimeoutExpired:return {**base,'status':'error','reason':'provider_timeout'}
    except Exception as exc:return {**base,'status':'error','reason':'provider_failed','error_type':type(exc).__name__}
