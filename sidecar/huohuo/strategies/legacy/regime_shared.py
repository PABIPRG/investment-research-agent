# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
from .runtime import time
from collections import deque
from typing import Iterable, Optional, Sequence
from .store import JsonStore
_INDEX_COLLECTION = 'market_index'
_REGIME_COLLECTION = 'market_regime'
_LATEST_KEY = '_latest'
__all__ = ['classify_regime', 'record_index_close', 'classify_and_store', 'latest_regime', 'refresh_and_classify', '_INDEX_COLLECTION', '_REGIME_COLLECTION']
