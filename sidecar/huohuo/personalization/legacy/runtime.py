from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace

_current = ContextVar('personalization_snapshot')
settings = SimpleNamespace(personalized_behavior_hours=168,personalized_comment_enabled=False,
    personalized_comment_ttl=1800,local_learning_retention_days=90,risk_event_deadline=2,
    llm_available=lambda:False)

@contextmanager
def runtime(snapshot):
    token=_current.set(snapshot)
    try: yield
    finally: _current.reset(token)
