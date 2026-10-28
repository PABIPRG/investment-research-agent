"""实例所有的数据和派生缓存，无模块级可变状态。"""
from copy import deepcopy
from functools import wraps
from pathlib import Path
from .seed_validation import read_json


def memoized(function):
    @wraps(function)
    def call(self, *args):
        key = (function.__name__, args)
        with self._lock:
            if key not in self._memo:
                self._memo[key] = function(self, *args)
            return self._memo[key]
    return call


class RepositoryBase:
    def __init__(self, seed, lock):
        self.seed, self._lock = seed, lock
        self._caches, self._memo = {}, {}
        self.document = {}
        self.version = None

    def configure(self, version, document):
        if self.version != version:
            self._caches.clear()
            self._memo.clear()
            self.document = deepcopy(document)
            self.version = version

    def _load(self, name):
        with self._lock:
            if name not in self._caches:
                directory = self.seed.data_path()
                if directory is None:
                    raise FileNotFoundError('请先在设置中确认下载产业链数据')
                self._caches[name] = read_json(Path(directory) / name)
            return self._caches[name]

    def load_overlay(self):
        return self.document.get('companies', {})

    def universe_index(self):
        return {r['code']: r for r in self.document.get('universe', [])}

    def _llm_links(self):
        # 名称为旧算法兼容；这里只读取经确认的结构化候选，不调用模型。
        return self.document.get('inferred_links', [])
