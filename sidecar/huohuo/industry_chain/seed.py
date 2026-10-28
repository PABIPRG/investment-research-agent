"""有界下载后原子切换 generation；失败保持原版本，启动只读取状态。"""
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
import requests
from .seed_validation import SEED_FILES, SOURCE_URL, NOTICE, MAX_FILE_BYTES, MAX_TOTAL_BYTES, read_json, validate_file, validate_dataset


def atomic_json(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(value, file, ensure_ascii=False, allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
        if hasattr(os, 'O_DIRECTORY'):
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class SeedData:
    def __init__(self, root, *, http_get=None, clock=time.time, lock=None, max_file=MAX_FILE_BYTES, max_total=MAX_TOTAL_BYTES):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError('产业链数据目录不能是符号链接')
        self.http_get, self.clock = http_get or requests.get, clock
        self.lock = lock or threading.RLock()
        self.max_file, self.max_total = max_file, max_total
        self.pointer = self.root / 'CURRENT.json'
        self.busy = False
        self.error = None
        self._validation = None

    def current(self):
        if not self.pointer.exists():
            return {'generation': None, 'operation_id': None}
        if self.pointer.is_symlink():
            raise ValueError('种子索引不能是符号链接')
        value = read_json(self.pointer)
        generation = value.get('generation')
        if generation is not None and (not isinstance(generation, str) or not re.fullmatch(r'seed-[a-f0-9]{32}', generation)):
            raise ValueError('种子索引无效')
        return value

    def data_path(self):
        value = self.current()
        return self.root / value['generation'] if value['generation'] else None

    def status(self):
        with self.lock:
            current = self.current()
            directory = self.data_path()
            valid, problem = False, None
            if directory:
                try:
                    if directory.is_symlink():
                        raise ValueError('种子目录不能是符号链接')
                    signature = tuple((name, (directory/name).stat().st_mtime_ns, (directory/name).stat().st_size) for name in SEED_FILES)
                    if self._validation != (current['generation'], signature):
                        files = validate_dataset(directory, self.max_file, self.max_total)
                        if files != current.get('files'):
                            raise ValueError('种子完整性校验失败')
                        self._validation = (current['generation'], signature)
                    valid = True
                except (ValueError, OSError, TypeError, KeyError):
                    problem = '本地种子不完整或校验失败，请重新确认下载'
            return {'state': 'downloading' if self.busy else 'ready' if valid else 'error' if (problem or self.error) else 'missing',
                    'available': valid, 'generation': current.get('generation'), 'downloaded_at': current.get('downloaded_at'),
                    'bytes': sum(x['bytes'] for x in current.get('files', {}).values()) if valid else 0,
                    'error': problem or self.error, 'source': NOTICE, 'limits': {'file_bytes': self.max_file, 'total_bytes': self.max_total},
                    'operation_id': current.get('operation_id')}

    def download(self, operation_id, *, refresh=False):
        with self.lock:
            if self.busy:
                raise RuntimeError('产业链下载正在进行，请查看状态，不要重复提交')
            if self.status()['available'] and not refresh:
                return self.status()
            self.busy, self.error = True, None
        staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=self.root))
        try:
            total = 0
            for name in SEED_FILES:
                target = staging / name
                with self.http_get(f'{SOURCE_URL}/{name}', timeout=(5, 60), stream=True, allow_redirects=False) as response:
                    if response.status_code != 200:
                        raise ValueError(f'{name} 下载失败（HTTP {response.status_code}）')
                    declared = int(response.headers.get('Content-Length') or 0)
                    if declared > self.max_file or total + declared > self.max_total:
                        raise ValueError('种子下载超过大小限制')
                    size = 0
                    with target.open('xb') as file:
                        for chunk in response.iter_content(65536):
                            if not chunk:
                                continue
                            size += len(chunk)
                            total += len(chunk)
                            if size > self.max_file or total > self.max_total:
                                raise ValueError('种子下载超过大小限制')
                            file.write(chunk)
                        file.flush()
                        os.fsync(file.fileno())
                validate_file(target, name, self.max_file)
            files = validate_dataset(staging, self.max_file, self.max_total)
            generation = 'seed-' + uuid.uuid4().hex
            with self.lock:
                old = self.data_path()
                os.replace(staging, self.root / generation)
                try:
                    atomic_json(self.pointer, {'generation': generation, 'operation_id': operation_id, 'downloaded_at': self.clock(), 'source': SOURCE_URL, 'files': files})
                except BaseException:
                    shutil.rmtree(self.root / generation, ignore_errors=True)
                    raise
                self._validation = None
                if old:
                    shutil.rmtree(old, ignore_errors=True)
            with self.lock:
                self.busy = False
            return self.status()
        except Exception:
            self.error = '本次下载未完成，原有数据保持不变；请检查来源可用性后重新确认'
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            with self.lock:
                self.busy = False

    def delete(self, operation_id):
        with self.lock:
            if self.busy:
                raise RuntimeError('下载进行中，暂不能删除')
            old = self.data_path()
            atomic_json(self.pointer, {'generation': None, 'operation_id': operation_id})
            self._validation, self.error = None, None
            if old:
                shutil.rmtree(old, ignore_errors=True)
            return self.status()
