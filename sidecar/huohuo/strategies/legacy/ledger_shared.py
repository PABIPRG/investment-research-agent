# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
import re
from .runtime import time
from datetime import date as _date
from .store import JsonStore
_LEDGER_COLLECTION = 'events_ledger'
_DEFAULT_TYPE = 'unknown'
_DATE_RE = re.compile('(\\d{4}-\\d{2}-\\d{2})')
__all__ = ['event_type_of', 'event_date_of', 'pool_id', 'record_candidate', 'symbol_pool', 'pool_stats', '_LEDGER_COLLECTION']
