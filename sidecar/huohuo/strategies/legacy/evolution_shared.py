# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
import hashlib
import json
import re
import secrets
import threading
from .runtime import time
from datetime import datetime
from .config import settings
from .store import JsonStore
from .strategies import _str2md5
_MUTABLE_KINDS = ('ma_cross', 'rsi_reversal', 'momentum', 'breakout', 'bollinger', 'volume_breakout')
_PREVIEW_COLLECTION = 'evolution_previews'
_CURRENT_PREVIEW_KEY = '_current'
_CLOSED_LOOP_RUNTIME_KEY = '_closed_loop_runtime'
_PREVIEW_TTL_SECONDS = 30 * 60
_EVOLUTION_LOCK = threading.Lock()
_STRATEGY_ID_PATTERN = re.compile('^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$')
class EvolutionPreviewConflict(RuntimeError):
    """待确认预案已失效、已提交或与当前业务状态不一致。"""
class EvolutionStrategyNotFound(LookupError):
    """指定的策略不存在，禁止回退到全局进化数据。"""
