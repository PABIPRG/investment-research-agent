"""来源相邻状态去重；A→B→A 是三次转换，不是两个全局内容桶。"""
from datetime import datetime, timezone

from huohuo.contracts import Invalid, canonical, text
from huohuo.execution import digest


def source_event_is_current(db, event_id):
    """旧快照留作历史，不因恢复委托或迟到结果重新取得当前资格。"""
    if not event_id or not event_id.startswith('SRC_'):
        return True
    row = db.execute('''SELECT h.event_id FROM source_versions v JOIN source_heads h
                        ON h.principal=v.principal AND h.scope_key=v.scope_key AND h.source=v.source
                        WHERE v.event_id=?''', (event_id,)).fetchone()
    return row is not None and row[0] == event_id


def record_source_transition(db, *, principal, scope_key, entity_id, source, version, document, observed_at):
    """在调用方写事务内保存来源快照和当前头，返回 (event_id, changed)。

    调用方必须用同一事务在 changed=True 时 record_event，失败由整个事务回滚。
    本函数不自行提交、不启动事务、不发通知、不修改已存在的来源快照。
    """
    if not db.in_transaction:
        raise Invalid("来源转换必须处于调用方的写事务中")
    for value, name in ((principal, "principal"), (scope_key, "scope_key"), (entity_id, "entity_id"),
                        (source, "source"), (version, "content_version")):
        text(value, name, 300)
    if not isinstance(document, dict):
        raise Invalid("来源文档必须为对象")
    try:
        stamp = datetime.fromisoformat(observed_at)
        if stamp.tzinfo is None:
            raise ValueError()
        observed_at = stamp.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        raise Invalid("来源观察时间需明确时区") from None
    head = db.execute(
        "SELECT event_id,content_version FROM source_heads WHERE principal=? AND scope_key=? AND source=?",
        (principal, scope_key, source),
    ).fetchone()
    if head is not None and head[1] == version:
        return head[0], False
    previous = head[0] if head else None
    event_id = "SRC_" + digest(["adjacent-source-v1", principal, scope_key, source, previous, version])
    db.execute("INSERT INTO source_versions(event_id,principal,subject,scope_key,source,version,document,observed_at) VALUES(?,?,?,?,?,?,?,?)",
               (event_id, principal, entity_id, scope_key, source, version, canonical(document), observed_at))
    db.execute("INSERT INTO source_heads(principal,scope_key,source,event_id,content_version,updated_at) VALUES(?,?,?,?,?,?) "
               "ON CONFLICT(principal,scope_key,source) DO UPDATE SET event_id=excluded.event_id,content_version=excluded.content_version,updated_at=excluded.updated_at",
               (principal, scope_key, source, event_id, version, observed_at))
    return event_id, True
