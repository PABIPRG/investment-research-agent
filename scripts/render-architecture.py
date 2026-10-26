"""从 Markdown 中标记的 Mermaid 图生成 SVG；不维护第二份节点/边。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/architecture'
DOC = ROOT / 'docs/当前架构与装配.md'
CONFIG = OUT / 'mermaid-config.json'
MANIFEST = OUT / 'diagram-manifest.json'
PATTERN = r'<!-- diagram: ([a-z-]+) -->\s*```mermaid\n(.*?)```'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只核对已生成文件，不启动浏览器')
    args = parser.parse_args()
    diagrams = re.findall(PATTERN, DOC.read_text(), re.S)
    if len(diagrams) != 5 or len({name for name, _ in diagrams}) != len(diagrams):
        raise ValueError('架构入口必须明确标记五张图，名称不能重复')
    brief = (ROOT / 'docs/设计基线/V1.4-团队Brief.md').read_text()
    baseline = re.findall(r'```mermaid\n(.*?)```', brief, re.S)
    if [body.strip() for _, body in diagrams[:2]] != [body.strip() for body in baseline[:2]]:
        raise ValueError('产品与业务主图偏离 V1.4 Brief；不能用工程补充替换基线')
    config_hash = digest(CONFIG.read_bytes())
    if args.check:
        manifest = json.loads(MANIFEST.read_text())
        if manifest['config_sha256'] != config_hash:
            raise ValueError('渲染配置已变，须重新生成')
        if set(manifest['diagrams']) != {name for name, _ in diagrams}:
            raise ValueError('图清单不一致')
        for name, body in diagrams:
            source = (body.strip() + '\n').encode()
            record = manifest['diagrams'][name]
            if (OUT / f'{name}.mmd').read_bytes() != source or record['source_sha256'] != digest(source):
                raise ValueError(f'{name}: Mermaid 提取副本与正文不一致')
            if record['svg_sha256'] != digest((OUT / f'{name}.svg').read_bytes()):
                raise ValueError(f'{name}: SVG 与生成记录不一致')
        print('五张图来源和 SVG 指纹一致；两张主图与 V1.4 Brief 一致')
        return
    executable = os.environ.get('HUOHUO_MERMAID_CLI') or shutil.which('mmdc')
    if not executable:
        raise SystemExit('请在独立工具目录安装 @mermaid-js/mermaid-cli@11.12.0，并设置 HUOHUO_MERMAID_CLI；不得用手工 SVG 替代')
    version = subprocess.check_output([executable, '--version'], text=True).strip()
    if version != '11.12.0':
        raise SystemExit(f'需要 mermaid-cli 11.12.0，当前 {version}')
    records = {}
    with tempfile.TemporaryDirectory(prefix='huohuo-diagrams-') as temporary:
        temp = Path(temporary)
        for name, body in diagrams:
            source = (body.strip() + '\n').encode()
            mmd, svg = temp / f'{name}.mmd', temp / f'{name}.svg'
            mmd.write_bytes(source)
            command = [executable, '-i', str(mmd), '-o', str(svg), '-c', str(CONFIG), '-b', 'white', '-w', '1600']
            if os.environ.get('HUOHUO_PUPPETEER_CONFIG'):
                command += ['-p', os.environ['HUOHUO_PUPPETEER_CONFIG']]
            subprocess.run(command, check=True, timeout=90)
            records[name] = {'source_sha256': digest(source), 'svg_sha256': digest(svg.read_bytes())}
        # 所有图都成功后更新派生文件，避免留下半套渲染结果。
        for name, _ in diagrams:
            for suffix in ('.mmd', '.svg'):
                shutil.copyfile(temp / (name + suffix), OUT / (name + suffix))
    MANIFEST.write_text(json.dumps({'source': 'docs/当前架构与装配.md', 'renderer': f'@mermaid-js/mermaid-cli@{version}', 'config_sha256': config_hash, 'diagrams': records}, ensure_ascii=False, indent=2) + '\n')
    print('已由同一 Mermaid 源生成五张 SVG；未修改设计基线')


if __name__ == '__main__':
    main()
