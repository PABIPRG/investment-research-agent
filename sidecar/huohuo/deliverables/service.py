"""侧车拥有成果状态。整目录原子发布，manifest 绑定调用/主体/会话。"""
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import Invalid, canonical, text
from .formats import MEDIA, cell, json_bytes, render_file

MAX_FILE = 10 * 1024 * 1024
ID = re.compile(r'^[0-9a-f]{64}$')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def exact(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise Invalid('成果参数缺失或包含未允许字段')


def field_path(value, path):
    if not isinstance(path, list) or len(path) > 8 or any(not isinstance(k, str) or not k or len(k) > 100 for k in path):
        raise Invalid('来源字段路径无效')
    for key in path:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            raise Invalid('来源中不存在指定字段；不能猜测或补造')
    return value


class Deliverables:
    def __init__(self, workspace, evidence):
        self.root = Path(workspace).absolute() / '.huohuo-deliverables'
        self.evidence = evidence

    def _root(self):
        if self.root.is_symlink():
            raise Invalid('成果目录不可为符号链接')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _read(self, directory, filename, limit=MAX_FILE):
        path = directory / filename
        try:
            if directory.is_symlink() or not directory.is_dir() or path.is_symlink():
                raise Invalid('成果路径无效')
            with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)), 'rb') as file:
                raw = file.read(limit + 1)
            if len(raw) > limit:
                raise Invalid('成果文件超过大小限制')
            return raw
        except (OSError, ValueError):
            raise Invalid('成果文件不存在或不可读取') from None

    def _manifest(self, principal, artifact_id, session=None):
        if not isinstance(artifact_id, str) or not ID.fullmatch(artifact_id):
            raise Invalid('成果编号无效')
        self._root()
        directory = self.root / artifact_id
        try:
            manifest = json.loads(self._read(directory, 'manifest.json', 100_000))
        except (ValueError, KeyError):
            raise Invalid('成果不存在或记录损坏') from None
        if manifest['principal'] != principal or (session is not None and manifest['session'] != session):
            raise Invalid('成果不属于当前用户或对话')
        return directory, manifest

    def inspect(self, principal, session, artifact_id):
        _, manifest = self._manifest(principal, artifact_id, session)
        self.download(principal, artifact_id, session=session)
        self.download(principal, artifact_id, 'metadata', session=session)
        return manifest['public']

    def by_call(self, principal, session, call_id):
        text(call_id, '调用', 200)
        return self.inspect(principal, session, digest(canonical([principal, session, call_id]).encode()))

    def download(self, principal, artifact_id, part='file', session=None):
        directory, manifest = self._manifest(principal, artifact_id, session)
        if part not in ('file', 'metadata'):
            raise Invalid('成果文件类型无效')
        entry = manifest[part]
        raw = self._read(directory, entry['filename'])
        if digest(raw) != entry['sha256']:
            raise Invalid('成果文件已改变，不能当作原交付下载')
        return entry, raw

    def create(self, principal, session, call_id, spec):
        for name, value in [('用户', principal), ('会话', session), ('调用', call_id)]:
            text(value, name, 200)
        exact(spec, ('format', 'title', 'content_kind', 'evidence_ids', 'limitations', 'tables'),
              ('format', 'title', 'content_kind', 'evidence_ids', 'limitations'))
        if len(canonical(spec).encode()) > 1_000_000:
            raise Invalid('成果请求过大，请缩小表格')
        fmt = spec['format']
        if not isinstance(fmt, str) or fmt not in MEDIA or spec['content_kind'] not in ('evidence', 'model_analysis'):
            raise Invalid('成果格式或内容性质无效')
        title = text(spec['title'], '标题', 60)
        if re.search(r'[\\/\x00-\x1f<>:"|?*]', title) or title in ('.', '..'):
            raise Invalid('成果标题不能包含路径或特殊字符')
        if not isinstance(spec['limitations'], str) or len(spec['limitations']) > 4000:
            raise Invalid('必须提供数据限制说明（可为空）')
        ids = spec['evidence_ids']
        if not isinstance(ids, list) or len(ids) > 8 or any(not isinstance(i, str) or not 1 <= len(i) <= 200 for i in ids) or len(set(ids)) != len(ids):
            raise Invalid('证据编号列表无效，最多八条')
        if spec['content_kind'] == 'evidence' and not ids:
            raise Invalid('原始资料导出需要真实证据')
        fingerprint = digest(canonical(spec).encode())
        artifact_id = digest(canonical([principal, session, call_id]).encode())
        self._root()
        directory = self.root / artifact_id
        if directory.exists() or directory.is_symlink():
            _, manifest = self._manifest(principal, artifact_id, session)
            if manifest['fingerprint'] != fingerprint:
                raise Invalid('同一调用的成果参数发生冲突')
            return self.inspect(principal, session, artifact_id)
        sources = {eid: self.evidence(principal, session, eid) for eid in ids}
        for result in sources.values():
            if not isinstance(result, dict) or result.get('status') not in ('ok', 'empty', 'partial'):
                raise Invalid('来源没有可导出的成功或部分成功结果')
        tables = self._tables(spec, sources)
        created = datetime.now(timezone.utc).isoformat()
        metadata = {'schema_version': 1, 'title': title, 'format': fmt, 'content_kind': spec['content_kind'],
                    'created_at': created, 'evidence_ids': ids, 'sources': sources,
                    'limitations': spec['limitations'], 'columns': [{'name': t['name'], 'columns': t['columns']} for t in tables],
                    'null_semantics': 'null/空单元格表示未知或未提供，不是零；CSV 将空字符串与未知均表示为空。',
                    'csv_text_semantics': 'CSV 对前导零和公式起始文本增加单引号；机器无损消费请选择 JSON/XLSX。'}
        raw_metadata = json_bytes(metadata)
        raw = render_file(fmt, tables, metadata)
        if max(len(raw), len(raw_metadata)) > MAX_FILE:
            raise Invalid('成果超过 10 MiB，请缩小范围')
        filename = f'{title}-{artifact_id[:8]}.{fmt}'
        file = {'filename': filename, 'sha256': digest(raw), 'bytes': len(raw), 'media_type': MEDIA[fmt]}
        notes = {'filename': '交付说明.json', 'sha256': digest(raw_metadata), 'bytes': len(raw_metadata), 'media_type': MEDIA['json']}
        public = {'id': artifact_id, **file, 'title': title, 'format': fmt, 'created_at': created,
                  'content_kind': spec['content_kind'], 'evidence_ids': ids, 'limitations': spec['limitations'],
                  'file_path': str(directory / filename), 'metadata_path': str(directory / notes['filename']),
                  'download_url': f'/api/huohuo/deliverables/download?id={artifact_id}&part=file',
                  'metadata_url': f'/api/huohuo/deliverables/download?id={artifact_id}&part=metadata'}
        manifest = {'principal': principal, 'session': session, 'fingerprint': fingerprint,
                    'file': file, 'metadata': notes, 'public': public}
        staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=self.root))
        try:
            for name, content in [(filename, raw), (notes['filename'], raw_metadata), ('manifest.json', json_bytes(manifest))]:
                with (staging / name).open('xb') as file_out:
                    os.chmod(staging / name, 0o600)
                    file_out.write(content)
                    file_out.flush()
                    os.fsync(file_out.fileno())
            try:
                os.rename(staging, directory)
            except OSError:
                if not directory.exists():
                    raise
                _, prior = self._manifest(principal, artifact_id, session)
                if prior['fingerprint'] != fingerprint:
                    raise Invalid('同一调用的成果参数发生冲突')
                return self.inspect(principal, session, artifact_id)
            if os.name == 'posix':
                descriptor = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return public

    def _tables(self, spec, sources):
        raw = spec.get('tables', [])
        if not isinstance(raw, list) or len(raw) > 6 or (not raw and spec['format'] != 'json'):
            raise Invalid('需要一至六个表；原始 JSON 可以不指定表')
        tables, names, cells = [], {'交付说明'}, 0
        for table in raw:
            exact(table, ('name', 'columns', 'rows', 'evidence_id', 'records_path'), ('name', 'columns'))
            name = text(table['name'], '表名', 31)
            if re.search(r'[\\/\[\]:*?\x00-\x1f]', name) or name.casefold() in names:
                raise Invalid('表名无效或重复')
            names.add(name.casefold())
            columns = table['columns']
            if not isinstance(columns, list) or not 1 <= len(columns) <= 40:
                raise Invalid('表格须有一至四十列')
            keys = set()
            for column in columns:
                exact(column, ('key', 'label', 'type', 'unit'), ('key', 'label', 'type'))
                key = text(column['key'], '字段', 100)
                text(column['label'], '列名', 100)
                if column['type'] not in ('text', 'number', 'percent', 'date') or key in keys:
                    raise Invalid('字段类型无效或重复')
                keys.add(key)
                if 'unit' in column:
                    text(column['unit'], '单位', 50)
            if spec['content_kind'] == 'evidence':
                if 'rows' in table or table.get('evidence_id') not in sources:
                    raise Invalid('原始资料表必须引用证据，不接受模型提供行')
                rows = field_path(sources[table['evidence_id']], table.get('records_path', []))
            else:
                if 'evidence_id' in table or 'records_path' in table:
                    raise Invalid('模型整理表不能冒充原始证据表')
                rows = table.get('rows')
            if not isinstance(rows, list) or len(rows) > 5000 or any(not isinstance(row, dict) for row in rows):
                raise Invalid('来源字段必须是记录数组，每表最多五千行')
            if rows and spec['content_kind'] == 'evidence' and any(not any(key in row for row in rows) for key in keys):
                raise Invalid('列字段不存在于来源记录，不能用全空列伪装未知')
            cells += len(rows) * len(columns)
            if cells > 50000:
                raise Invalid('总单元格数超过五万')
            selected = []
            for row in rows:
                if spec['content_kind'] == 'model_analysis' and set(row) - keys:
                    raise Invalid('行包含未声明列')
                selected.append({c['key']: cell(row.get(c['key']), c) for c in columns})
            tables.append({'name': name, 'columns': columns, 'rows': selected})
        return tables
