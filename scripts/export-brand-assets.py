"""从已确认的透明母图导出 UI 资源；仅开发素材工具需要 Pillow。"""
from pathlib import Path
import hashlib
import json
from PIL import Image

root = Path(__file__).resolve().parent.parent
source = root / 'design/huohuo'
assets = root / 'product/ui/assets'
companion = assets / 'companion'

def trim(name):
    image = Image.open(source / name).convert('RGBA')
    # 生成母图边缘可能有极淡透明噪点；不让这些噪点挤小可见角色。
    bounds = image.getchannel('A').point(lambda alpha: 255 if alpha > 8 else 0).getbbox()
    assert bounds, f'{name}: 透明母图没有可见像素'
    return image.crop(bounds)

header = trim('header-peek-master.png')
header.resize((256, round(header.height * 256 / header.width)), Image.Resampling.LANCZOS).save(companion / 'header-peek.png')
idle = trim('idle-cheeks-master.png')
idle.thumbnail((224, 224), Image.Resampling.LANCZOS)
avatar = Image.new('RGBA', (256, 256))
avatar.alpha_composite(idle, ((256-idle.width)//2, (256-idle.height)//2))
avatar.save(assets / 'brand.png')
avatar.save(companion / 'fallback.png')
avatar.save(assets / 'favicon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])

manifest_path = companion / 'resource-manifest.json'
manifest = json.loads(manifest_path.read_text())
manifest['revision'] = 'r3-color-aligned'
manifest['displayGrade'] = {'chroma': 1.6, 'yellowCastCorrection': 0.04, 'appliesTo': 'SpiritBody', 'reference': 'header-peek.png'}
manifest['origin'] = '保留既有 12 动作 GLB；采用已批准的放大镜扒栏图标和暖橙柔粉腮红，母版见 design/huohuo'
for name in ['header-peek.png', 'fallback.png', 'renderer.js']:
    manifest['sha256'][name] = hashlib.sha256((companion / name).read_bytes()).hexdigest()
manifest['brandSha256'] = {name: hashlib.sha256((assets / name).read_bytes()).hexdigest() for name in ['brand.png', 'favicon.ico']}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print('已导出 header-peek、brand、fallback、favicon，并更新资源指纹')
