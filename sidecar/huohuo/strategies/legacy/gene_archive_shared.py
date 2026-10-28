# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
import hashlib
from .runtime import time
from typing import Optional
from .store import JsonStore
_GENE_ARCHIVE_COLLECTION = 'gene_archive'
__all__ = ['archive_record', 'revival_candidates', 'all_archived', 'reactivate_archived', '_GENE_ARCHIVE_COLLECTION']
