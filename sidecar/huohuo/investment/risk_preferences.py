"""偏好调整、文本候选与预算视图；不写状态、不调用模型。"""
import copy
import math
import re
from ..contracts import Invalid, text
from .risk_profiles import RISK_PROFILES
from .risk_questionnaire import BANK, TIERS, LABELS
from .risk_text_rules import _RULE_ANSWERS

ORDER = tuple(LABELS)


def adjust(current, payload):
    if not current:
        raise Invalid('请先完成并保存风险偏好问卷，再手动调整')
    if not isinstance(payload, dict) or set(payload) != {'risk_tolerance', 'horizon_years'}:
        raise Invalid('调整须明确风险承受度和投资期限')
    risk, horizon = payload['risk_tolerance'], payload['horizon_years']
    if type(risk) not in (int, float) or not math.isfinite(risk) or not 0 <= risk <= 1:
        raise Invalid('风险承受度须为 0 至 1 的有限数值')
    if type(horizon) is not int or not 1 <= horizon <= 30:
        raise Invalid('投资期限须为 1 至 30 的整数年')
    idx = round(2*risk)
    if horizon < 2: idx = min(idx, 1)
    elif horizon >= 5: idx = max(idx, 1)
    value = copy.deepcopy(current)
    value['inferred_profile'] = current.get('inferred_profile', current['profile'])
    value.update(profile=ORDER[idx], label=LABELS[ORDER[idx]], manual_adjust=dict(payload), method='manual_adjust')
    return value


def policy(current):
    if not current: return None
    return {'profile': current['profile'], 'inferred_profile': current.get('inferred_profile', current['profile']),
            **copy.deepcopy(RISK_PROFILES[current['profile']]), 'policy_version': 'legacy-v1',
            'basis': '用户确认的有效风险偏好；预算用于研究解释与建议护栏，不授权交易或通知。'}


def parse(body):
    if not isinstance(body, dict) or not {'tier','text'} <= set(body) or set(body) - {'tier','text','candidates'}:
        raise Invalid('解析须包含问卷类型、原文和可选答案候选')
    tier = body['tier']
    if not isinstance(tier,str) or tier not in TIERS: raise Invalid('问卷类型无效')
    statement = text(body['text'], '偏好描述', 4000)
    candidates = body.get('candidates')
    if candidates is not None and (not isinstance(candidates,list) or len(candidates)>len(TIERS[tier])):
        raise Invalid('答案候选格式无效')
    answers, warnings = {}, []
    for item in candidates or []:
        if not isinstance(item,dict) or set(item)!={'qid','option'}: raise Invalid('候选只能包含题目与选项')
        qid, option = item['qid'], item['option']
        if not isinstance(qid,str) or qid not in TIERS[tier] or qid in answers: raise Invalid('候选包含未知或重复题目')
        if type(option) is not int or not 0<=option<len(BANK[qid]['options']): raise Invalid('候选选项无效')
        answers[qid]={'qid':qid,'option':option,'label':BANK[qid]['options'][option]['label'],'source':'dsh_candidate'}
    if candidates is None:
        # 保留旧关键词资产；多档命中或否定句不沿用旧版“第一个匹配即答案”。
        negated = bool(re.search(r'不是|不能|不想|不愿|无法|没想好|不确定|并非|不接受', statement))
        for qid in TIERS[tier]:
            matches=[]
            for keywords,label,_score in _RULE_ANSWERS[qid]:
                hits=[k for k in keywords if k in statement]
                if qid=='goal' and '收入' in statement:
                    hits=[k for k in hits if k not in ('稳定','安全')]
                if hits: matches.append((label,hits))
            # 高具体度锚点覆盖同一词中较短的锚点，例如“收入不稳定/稳定”。
            matches=[m for m in matches if not all(any(k in other for label,ks in matches if label!=m[0] for other in ks) for k in m[1])]
            if negated or len(matches)>1:
                if matches: warnings.append({'qid':qid,'reason':'描述含否定、冲突或多个档位，请自行选择或通过对话澄清'})
                continue
            if matches:
                label=matches[0][0]
                option=next(i for i,o in enumerate(BANK[qid]['options']) if o['label']==label)
                answers[qid]={'qid':qid,'option':option,'label':label,'source':'legacy_rules','anchors':matches[0][1]}
    return {'tier':tier,'statement':statement,'answers':[answers[q] for q in TIERS[tier] if q in answers],
            'missing':[q for q in TIERS[tier] if q not in answers], 'warnings':warnings,
            'requires_confirmation':True,'saved':False,'notice':'解析仅填入待核对答案；补齐并明确确认后才按题库计分保存。'}
