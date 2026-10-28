# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""旧算法的显式实例上下文；不读取旧环境、账户、目录或服务。"""
import json
import time as system_time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

DEFAULTS = json.loads(Path(__file__).with_name('defaults.json').read_text())
_current = ContextVar('strategy_runtime')
class Policy:
    def __getattr__(self, key): return getattr(_current.get()[0], key)
    def snapshot(self): return vars(_current.get()[0]).copy()
class Clock:
    def time(self): return _current.get()[1]()
    def localtime(self, value=None): return system_time.gmtime(self.time() if value is None else value)
    def strftime(self, fmt, value=None): return system_time.strftime(fmt, self.localtime() if value is None else value)
    def __getattr__(self,key):return getattr(system_time,key)
settings = Policy()
time = Clock()
@contextmanager
def runtime(clock, policy=None):
    value = DEFAULTS.copy()
    if policy:value.update(policy)
    token = _current.set((SimpleNamespace(**value),clock))
    try:yield
    finally:_current.reset(token)
