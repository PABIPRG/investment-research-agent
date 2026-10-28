"""研究是否需要比较基准由已确认规则决定，不由模型或来源状态决定。"""
from collections.abc import Mapping


def requires_comparison_baseline(policy):
    """绝对阈值、定时交付和直接提醒不需要过去的研究结果。

    语义重要变化以及包含它的组合条件仍需先建立基准。此函数只决定
    既有任务的准入，不创建任务、不重试失败，也不改变用户联系授权。
    无法识别的规则保守保留基准门禁，正式规则校验仍由 contact_policy 负责。
    """
    if not isinstance(policy, Mapping):
        return True
    mode = policy.get('mode', 'condition')
    if mode in {'scheduled_delivery', 'due_reminder'}:
        return False
    if mode not in {'condition', 'periodic_check'}:
        return True
    return _condition_requires_comparison(policy.get('condition'))


def _condition_requires_comparison(condition, depth=0):
    if depth > 4 or not isinstance(condition, Mapping):
        return True
    kind = condition.get('type')
    if kind == 'numeric':
        # numeric 的当前契约只允许固定数值 threshold，不支持历史值或模型表达式。
        import math
        threshold = condition.get('threshold')
        return not (type(threshold) in (int, float) and math.isfinite(threshold)
                    and condition.get('operator') in {'>', '>=', '<', '<=', '==', '!='}
                    and isinstance(condition.get('metric'), str) and bool(condition['metric']))
    if kind in {'all', 'any'}:
        children = condition.get('conditions')
        if not isinstance(children, list) or not 1 <= len(children) <= 8:
            return True
        return any(_condition_requires_comparison(child, depth + 1) for child in children)
    return True
