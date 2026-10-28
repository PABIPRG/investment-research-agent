"""旧委托只有重新确认完整范围与联系规则后，才可恢复执行。"""
from datetime import datetime, timezone
from ..contracts import Invalid


def needs_review(view):
    return view['revision']['basis'].get('legacy_import', {}).get('requires_review') is True


def reviewed_basis(store, view, body):
    basis = dict(view['revision']['basis'])
    if not needs_review(view):
        return basis
    if 'contact_rule' not in body or 'contact_channels' not in body:
        raise Invalid('旧委托需明确重新确认研究范围、联系规则和渠道，再恢复跟进')
    at = datetime.now(timezone.utc)
    # 已确认的新修订替代旧范围；保留旧待办和修订，记录其关闭原因与时间。
    closed = []
    for requirement in store.list_requirements(view['mandate']['mandate_id'], status='open'):
        store.update_requirement(requirement.requirement_id,
                                 status='resolved' if requirement.code == 'legacy_import_review' else 'waived',
                                 resolved_at=at)
        closed.append(requirement.requirement_id)
    basis['legacy_import'] = {**basis['legacy_import'], 'requires_review': False,
                              'reviewed_at': at.isoformat(),
                              'reviewed_revision': view['mandate']['current_revision'] + 1,
                              'superseded_requirements': closed}
    return basis
