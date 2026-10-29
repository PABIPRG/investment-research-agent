// 先以独立端口运行 smoke-skills --serve --deliverables；不使用真实模型或来源。
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises'
import { resolve, join } from 'node:path'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
const root=resolve('.'),out=resolve(process.env.HUOHUO_SMOKE_OUT??'artifacts/deliverables-uat')
const runtime=JSON.parse(await readFile(join(out,'runtime.json'),'utf8'))
const config=JSON.parse(await readFile(join(runtime.instance,'instance.json'),'utf8'))
const {chromium}=await import(process.env.HUOHUO_PLAYWRIGHT??'playwright')
const browser=await chromium.launch({headless:true,channel:'chrome'})
const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light',acceptDownloads:true})
const page=await context.newPage(),errors=[]
page.on('pageerror',e=>errors.push(e.message))
const report={status:'not-tested',model:'controlled',source:'synthetic',checks:[],screenshots:[],files:[]}
const pass=name=>report.checks.push({name,status:'passed'})
const downloads=join(out,'downloads');await mkdir(downloads,{recursive:true})
async function save(button, suffix){
 const pending=page.waitForEvent('download',{timeout:15000});await button.click();const download=await pending
 const path=join(downloads,suffix+'-'+download.suggestedFilename());await download.saveAs(path)
 const bytes=await readFile(path);report.files.push({name:download.suggestedFilename(),bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});return {path,bytes}
}
try{
 await page.goto(runtime.launchUrl)
 const intro=page.getByRole('button',{name:'继续',exact:true})
 await intro.or(page.locator('[contenteditable="true"]').first()).first().waitFor({timeout:30000})
 if(await intro.isVisible())await intro.click()
 await page.locator('[contenteditable="true"]').first().waitFor();
 await page.getByRole('button',{name:'我的委托',exact:true}).click();await page.getByRole('button',{name:'对话',exact:true}).first().click();
 pass('通过当前认证入口进入真实火火首页')
 await page.waitForTimeout(750) // 等待现有首页入场与会话创建完成，避免在旧输入框上填草稿。
 for(const format of ['CSV','JSON','Excel']){
  const editor=page.locator('[contenteditable="true"]').first();await editor.fill('交付回放 '+format);await page.getByRole('button',{name:'发送消息',exact:true}).click()
  await page.getByText(`已生成 ${format.toUpperCase()} 合成研究成果`,{exact:false}).last().waitFor({timeout:30000})
  const cards=page.locator('[data-presented-file]')
  const mainCard=cards.filter({hasText:format==='Excel'?/\.xlsx/:format==='CSV'?/\.csv/:/银行研究成果.*\.json/}).last()
  await mainCard.waitFor({timeout:10000})
  assert.equal(await mainCard.locator(':scope > button').isVisible(),false,'下载卡片不显示未接入的侧边预览动作')
  const main=await save(mainCard.getByRole('button',{name:'下载',exact:true}),format)
  const notes=await save(cards.last().getByRole('button',{name:'下载',exact:true}),format+'-notes')
  const metadata=JSON.parse(notes.bytes.toString());assert.equal(metadata.content_kind,'evidence');assert.equal(metadata.sources[metadata.evidence_ids[0]].data.records[0].code,'000001')
  if(format==='JSON'){const data=JSON.parse(main.bytes.toString());assert.equal(data.sources[metadata.evidence_ids[0]].data.records[0].cost,null)}
  else execFileSync(config.python,['-c',format==='Excel'?`import sys,openpyxl
w=openpyxl.load_workbook(sys.argv[1]);s=w['对比数据'];assert s['A2'].value=='000001';assert s['D2'].value is None;assert s['D3'].value==0;assert s['G2'].data_type=='s';assert s['G2'].value=='=1+1';assert s['E2'].number_format=='0.00%';assert s.freeze_panes=='A2'`:`import sys,csv
r=list(csv.reader(open(sys.argv[1],encoding='utf-8-sig',newline='')));assert r[1][0]=="'000001";assert r[1][3]=='';assert r[2][3]=='0';assert r[1][6]=="'=1+1"`,main.path])
  pass(format+'：真实聊天加载 Skill、读取证据、生成并下载，解析核对内容与未知值')
  await page.screenshot({path:join(out,`uat-${format}-1440-light.png`),fullPage:true});report.screenshots.push(`uat-${format}-1440-light.png`)
  const hash=createHash('sha256').update(main.bytes).digest('hex')
  await page.reload();await page.locator('[contenteditable="true"]').first().waitFor();await page.waitForTimeout(1000)
  await page.getByRole('button',{name:'历史对话',exact:true}).click()
  await page.getByRole('dialog').locator('li button').filter({hasText:'成果受控验收'}).first().click();await mainCard.waitFor({timeout:15000})
  await page.waitForFunction(()=>!document.querySelector('[data-huohuo-conversation]')?.hasAttribute('data-history-transition'))
  const again=await save(mainCard.getByRole('button',{name:'下载',exact:true}),format+'-reload')
  assert.equal(createHash('sha256').update(again.bytes).digest('hex'),hash);pass(format+'：刷新后同一成果字节不变')
 }
 for(const width of [1024,768,390]){
  await page.setViewportSize({width,height:900});assert.ok(await page.getByRole('button',{name:'下载',exact:true}).count()>=6)
  await page.waitForTimeout(750) // 检查稳定布局；历史入场与响应跟随动画最长约 600ms。
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))
  assert.ok(await page.evaluate(()=>{
    const mascot=document.querySelector('[data-huohuo-companion]')?.getBoundingClientRect()
    const file=[...document.querySelectorAll('[data-presented-file]')].findLast(e=>e.textContent.includes('.xlsx'))?.getBoundingClientRect()
    return !mascot||!file||mascot.right<=file.left||mascot.left>=file.right||mascot.bottom<=file.top||mascot.top>=file.bottom
  }),'稳定布局下火火不能遮挡成果卡片')
  await page.screenshot({path:join(out,`uat-${width}-light.png`),fullPage:true});report.screenshots.push(`uat-${width}-light.png`);pass(width+'px 下载操作保留且页面无横向溢出')
 }
 await page.setViewportSize({width:1440,height:1000});await page.emulateMedia({colorScheme:'dark'});await page.waitForTimeout(750)
 const contrast=await page.locator('[data-presented-file]').last().evaluate(e=>{
  const rgb=s=>s.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4})
  const lum=s=>rgb(s).reduce((n,v,i)=>n+v*[0.2126,0.7152,0.0722][i],0)
  const style=getComputedStyle(e),a=lum(style.color),b=lum(style.backgroundColor)
  return (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)
 });assert.ok(contrast>=4.5,'深色文件名对比度不足：'+contrast);pass('深色交付卡片文件名对比度符合 4.5:1')
 await page.screenshot({path:join(out,'uat-1440-dark.png'),fullPage:true});report.screenshots.push('uat-1440-dark.png')
 const first=page.locator('[data-presented-file]').filter({hasText:/\.xlsx/}).last().getByRole('button',{name:'下载',exact:true})
 await page.route('**/api/huohuo/deliverables/download?*',route=>route.fulfill({status:503,body:'fixture download unavailable'}))
 await first.click();await page.getByText('下载失败，请重试；成果可能已缺失。',{exact:true}).waitFor();pass('下载失败可见且不重做研究')
 await page.screenshot({path:join(out,'uat-download-failure.png'),fullPage:true});report.screenshots.push('uat-download-failure.png')
 await page.unroute('**/api/huohuo/deliverables/download?*')
 await save(page.getByRole('button',{name:'重试下载',exact:true}),'retry');pass('重试下载同一成果成功')
 // 移动的仅是本脚本新建实例内最后一份主成果，随后立即恢复。
 const dirs=await import('node:fs/promises').then(m=>m.readdir(join(config.workspace,'.huohuo-deliverables')))
 const manifests=await Promise.all(dirs.filter(x=>!x.startsWith('.')).map(async x=>JSON.parse(await readFile(join(config.workspace,'.huohuo-deliverables',x,'manifest.json'),'utf8'))))
 const latest=manifests.sort((a,b)=>a.public.created_at.localeCompare(b.public.created_at)).at(-1)
 const source=latest.public.file_path;await rename(source,source+'.uat-missing')
 try{await first.click();await page.getByText('下载失败，请重试；成果可能已缺失。',{exact:true}).waitFor();pass('源文件缺失明确失败，不下载残件')}finally{await rename(source+'.uat-missing',source)}
 const unauth=await browser.newContext();const rejected=await unauth.request.get(`http://127.0.0.1:${runtime.web}/api/huohuo/deliverables/download?id=${latest.public.id}`);assert.ok([401,403].includes(rejected.status()));await unauth.close();pass('未登录浏览器不能下载成果')
 const forbidden=await context.request.get(`http://127.0.0.1:${runtime.web}/api/huohuo/deliverables/download?id=../../business.sqlite`);assert.equal(forbidden.status(),400);pass('认证后仍拒绝任意路径')
 assert.deepEqual(errors,[]);pass('浏览器无 pageerror');report.status='passed'
}catch(error){report.status='failed';report.error=String(error);report.visible_text=(await page.locator('body').innerText()).slice(-5000);await page.screenshot({path:join(out,'uat-failure.png'),fullPage:true});throw error}
finally{await browser.close();await writeFile(join(out,'uat-report.json'),JSON.stringify(report,null,2))}
