"""固定种子的边界、结构与来源；不把第三方公开托管等同于再分发许可。"""
import hashlib
import json
from pathlib import Path

SEED_FILES = ('stats.json', 'companies.json', 'market-caps.json', 'view-data-all.json', 'network-data.json')
SOURCE_URL = 'https://villadora.github.io/iducsite/data'
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
NOTICE = {
    'name': 'IDUXGRAPH / iducsite',
    'url': 'https://villadora.github.io/iducsite/',
    'repository': 'https://github.com/villadora/iducsite',
    'license_status': 'not_verified',
    'notice': '第三方数据仅供研究参考，含算法推断；不构成投资建议。尚未核实可再分发或商业使用许可；产品不打包分发种子。下载前请确认自己的用途获准，使用结论应核对原始披露。',
}


def reject_constant(value):
    raise ValueError('JSON 不允许非有限数值')


def read_json(path):
    with Path(path).open(encoding='utf-8') as file:
        return json.load(file, parse_constant=reject_constant)


def validate(name, value):
    if name == 'stats.json':
        valid = isinstance(value, dict) and bool(value)
    elif name == 'companies.json':
        valid = isinstance(value, list) and bool(value) and all(isinstance(x, dict) and isinstance(x.get('code'), str) and isinstance(x.get('name'), str) for x in value)
    elif name == 'market-caps.json':
        valid = isinstance(value, dict) and bool(value) and all(isinstance(x, dict) for x in value.values())
    elif name == 'view-data-all.json':
        records = value.get('companies') if isinstance(value, dict) else None
        valid = isinstance(records, dict) and bool(records)
        if valid:
            for record in records.values():
                if not isinstance(record, dict):
                    valid = False
                    break
                for group, relation in (('materials', 'suppliers'), ('products', 'customers')):
                    groups = record.get(group) or []
                    if not isinstance(groups, list) or not all(isinstance(x, dict) for x in groups):
                        valid = False
                        break
                    for item in groups:
                        entries = item.get(relation) or []
                        if not isinstance(entries, list) or not all(isinstance(x, dict) for x in entries):
                            valid = False
                            break
    elif name == 'network-data.json':
        valid = isinstance(value, dict) and isinstance(value.get('nodes'), list) and bool(value['nodes']) and isinstance(value.get('links'), list)
        if valid:
            valid = all(isinstance(n, dict) and isinstance(n.get('id'), str) for n in value['nodes']) and all(isinstance(e, dict) and isinstance(e.get('source'), str) and isinstance(e.get('target'), str) for e in value['links'])
    else:
        valid = False
    if not valid:
        raise ValueError(f'{name} 不是有效的产业链种子格式')


def validate_file(path, name, max_bytes=MAX_FILE_BYTES):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'{name} 缺失或不是普通文件')
    size = path.stat().st_size
    if not 0 < size <= max_bytes:
        raise ValueError(f'{name} 超出文件大小限制')
    value = read_json(path)
    validate(name, value)
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(65536), b''):
            digest.update(chunk)
    return {'bytes': size, 'sha256': digest.hexdigest()}


def validate_dataset(path, max_file=MAX_FILE_BYTES, max_total=MAX_TOTAL_BYTES):
    files = {name: validate_file(Path(path) / name, name, max_file) for name in SEED_FILES}
    if sum(item['bytes'] for item in files.values()) > max_total:
        raise ValueError('产业链种子超过总大小限制')
    return files
