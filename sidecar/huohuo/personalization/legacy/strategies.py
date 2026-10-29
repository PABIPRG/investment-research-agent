import hashlib
from .runtime import _current

def fetch_events(limit=100,timeout=None):
    return _current.get()['events'][:limit]

def _str2md5(value):
    return hashlib.md5(value.encode()).hexdigest()

def fetch_events_with_status(limit=100,**kwargs):
    return fetch_events(limit),{'degraded':True,'status':'saved_snapshot','detail':'当前已保存事件快照，不保证实时或全市场完整覆盖'}
