"""生成无需外部依赖的工程示意 SVG；与同目录 Mermaid 源码共同审阅。"""
from pathlib import Path
from html import escape
root=Path(__file__).resolve().parent.parent/'docs/architecture'
root.mkdir(parents=True,exist_ok=True)
views={
'ownership':('运行与状态所有权','产品候选 · 固定 DSH · 单一权威实例',[
('distribution','安装、实例与后台进程生命周期'),('chat Profile','DSH Agent / 会话 / 模型 / Skill'),('worker Profile','一次有界 DSH 研究 · 单一工具'),('product','UI、工具桥与权限 guard'),('sidecar','实体 / 证据 / 委托 / 投资 / 通知'),('SQLite + DSH 存储','业务状态与会话配置分层持久化')],[(0,1),(0,2),(1,3),(2,4),(3,4),(4,5)]),
'skills':('一次聊天：按任务加载方法','目录和加载正文均进入上下文 · 工具 schema 仍常驻',[
('用户表达 + 常驻不变量','身份、权限、未知状态与证据边界'),('DSH 原生目录','只发现产品 bundled chat Skills'),('原生 skill loader','按任务加载研究 / 委托 / 投资方法'),('独立业务工具','48 研究工具及既有业务工具'),('guard + 可信 API','确认、授权、版本、幂等由程序校验'),('SQLite 回执 → 回复','已接受 / 已完成 / 未知分别表达')],[(0,1),(1,2),(2,3),(3,4),(4,5)]),
'background':('后台研究与联系流程','图示职责已落在领域代码 · 真模型、在线事件与外发未在本轮验收',[
('创建委托 / 资料版本事件','持久 outbox / inbox → 依赖匹配'),('业务 job → execution / attempt','版本、取消代次与 lease 绑定'),('有界 DSH 研究 → 证据准入','主体、期间、指标、来源、本次尝试'),('基准 / 复核 → 四值条件','met / unmet / unknown / error'),('核心决定 → 通知队列','渠道、静默、TTL 与失败分类'),('发送前复核 → 投递回执','授权与代次事务核对；unknown 对账')],[(0,1),(1,2),(2,3),(3,4),(4,5)])}
for key,(title,subtitle,nodes,edges) in views.items():
 w,h=1100,700;pos=[(65+(i%2)*530,145+(i//2)*170) for i in range(len(nodes))]
 s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{title}">','<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#587895"/></marker></defs>',f'<rect width="{w}" height="{h}" fill="#f7f9fb"/>',f'<text x="65" y="58" font-size="30" font-weight="700" fill="#18364a">{title}</text>',f'<text x="65" y="94" font-size="16" fill="#526b7c">{subtitle}</text>']
 for a,b in edges:
  x,y=pos[a];xx,yy=pos[b]
  if yy==y: path=f'M{x+440} {y+55} H{xx-8}'
  elif xx==x:path=f'M{x+220} {y+110} V{yy-8}'
  else:path=f'M{x+220} {y+110} V{y+140} H{xx+220} V{yy-8}'
  s.append(f'<path d="{path}" fill="none" stroke="#587895" stroke-width="2" marker-end="url(#arrow)"/>')
 for i,((label,desc),(x,y)) in enumerate(zip(nodes,pos)):
  s += [f'<rect x="{x}" y="{y}" width="440" height="110" rx="10" fill="white" stroke="#b6c8d6"/>',f'<text x="{x+20}" y="{y+35}" font-size="20" font-weight="600" fill="#18364a">{i+1}. {escape(label)}</text>',f'<text x="{x+20}" y="{y+73}" font-size="15" fill="#526b7c">{escape(desc)}</text>']
 s+=['<text x="65" y="665" font-size="14" fill="#526b7c">火火 · 2026-10-26 接力候选 | 受控验证与真实研究、发布分开记录</text>','</svg>']
 (root/(key+'.svg')).write_text('\n'.join(s))
# Markdown 为 Mermaid 图的事实源，提取单独文件，避免两份手工维护。
text=(root.parent/'当前架构与装配.md').read_text()
for name,block in zip(views,text.split('```mermaid\n')[1:]):(root/(name+'.mmd')).write_text(block.split('```',1)[0])
