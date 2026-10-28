# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
import hashlib
import json
import logging
import math
import re
import threading
from .runtime import time
import uuid
from datetime import date, timedelta
from typing import Callable
from .config import settings
from .store import JsonStore
KINDS = ('ma_cross', 'rsi_reversal', 'momentum', 'breakout', 'bollinger', 'volume_breakout')
VERIFICATION_STATUSES = frozenset({'passed', 'not_passed', 'insufficient'})
_ALLOWED_PREFIXES = ('0', '3', '6')
_LONLY = {'rsi_reversal': '超跌反弹', 'bollinger': '超跌反弹'}
_DEFAULT_PARAMS = {'ma_cross': {'fast': 5, 'slow': 20}, 'rsi_reversal': {'n': 14, 'oversold': 30, 'overbought': 70}, 'momentum': {'n': 10}, 'breakout': {'n': 20}, 'bollinger': {'n': 20, 'k': 2.0}, 'volume_breakout': {'n': 20, 'vol_mult': 1.5}}
_EVENTS_CACHE: dict[str, tuple[float, list[dict], int] | tuple[float, list[dict]]] = {}
_EVENTS_CACHE_LOCK = threading.Lock()
_EVENTS_REFRESH_LOCK = threading.Lock()
_EVENTS_FAILURE: tuple[float, str] | None = None
_EVENTS_CLOCK = time.time
