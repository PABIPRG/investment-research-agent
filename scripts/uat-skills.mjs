// 先运行 npm run smoke:skills -- --serve；浏览器库从显式环境变量或本机安装加载。
import assert from 'node:assert/strict'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
import {resolve,join} from 'node:path'
const root=resolve('.'),out=join(root,'artifacts/skills-smoke')
const runtime=JSON.parse(await readFile(join(out,'runtime.json'),'utf8'))
const config=JSON.parse(await readFile(join(runtime.instance,'instance.json'),'utf8'))
const {chromium}=await import(process.env.HUOHUO_PLAYWRIGHT??'playwright')
const browser=await chromium.launch({headless:true,channel:'chrome'})
const page=await browser.newPage({viewport:{width:1440,height:1000},colorScheme:'light'})
const errors=[];page.on('pageerror',e=>errors.push(e.message))
const report={status:'not-tested',model:'controlled',data:'synthetic',checks:[],screenshots:[]}
const pass=name=>report.checks.push({name,status:'passed'})
const api=async path=>{const r=await fetch(`http://127.0.0.1:${runtime.api}${path}`,{headers:{Authorization:`Bearer ${config.user_token}`}});assert.equal(r.status,200);return r.json()}
try{
 await page.goto(runtime.launchUrl)
 const next=page.getByRole('button',{name:'继续',exact:true});await next.waitFor({timeout:30000});await next.click()
 await page.getByRole('button',{name:'委托查询',exact:true}).click();await page.getByText('还没有委托。',{exact:false}).waitFor();pass('通过真实导航看到空委托状态')
 await page.getByRole('button',{name:'回到对话创建委托'}).click()
 const editor=page.locator('[contenteditable="true"]').first();await editor.fill('回放 U01：确认委托 600519 半年报收入研究，仅在产品内查看，不外发通知。');await editor.press('Enter')
 await page.getByText('贵州茅台 · 股票 · 600519',{exact:true}).waitFor({timeout:30000});await page.getByText('贵州茅台 · 股票 · 600519',{exact:true}).click();await page.getByRole('button',{name:/提交/}).last().click()
 await page.getByText('已保存合成验收委托。',{exact:false}).waitFor({timeout:30000});pass('聊天经两个原生 Skill 和真实对象确认创建委托')
 let data
 for(let i=0;i<120;i++){data=await api('/mandates');if(data.items[0]?.executions.some(e=>e.status==='succeeded'))break;await new Promise(r=>setTimeout(r,500))}
 const saved=data.items[0];assert.ok(saved?.baseline);assert.equal(saved.executions[0].status,'succeeded');assert.ok(saved.evidence.length);assert.equal(saved.notifications.length,0);pass('后台真实 DSH worker 与 API/SQLite 保存合成研究基准和证据，零通知')
 await page.getByRole('button',{name:'委托查询',exact:true}).click();await page.getByRole('button',{name:/合成半年报营业总收入研究/}).first().click()
 await page.getByText('初次研究与基准',{exact:true}).waitFor();await page.screenshot({path:join(out,'uat-1440-light.png'),fullPage:true});report.screenshots.push('uat-1440-light.png')
 await page.reload();await page.getByRole('button',{name:'委托查询',exact:true}).click();await page.getByRole('button',{name:/合成半年报营业总收入研究/}).first().click();await page.getByText('初次研究与基准',{exact:true}).waitFor();pass('刷新后通过导航重新回查同一基准')
 assert.equal((await api('/mandates')).items[0].mandate.mandate_id,saved.mandate.mandate_id)
 for(const width of [1024,768,390]){await page.setViewportSize({width,height:900});await page.screenshot({path:join(out,`uat-${width}.png`),fullPage:true});report.screenshots.push(`uat-${width}.png`);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));pass(`${width}px 无页面横向溢出`)}
 await page.setViewportSize({width:1440,height:1000});await page.emulateMedia({colorScheme:'dark'});await page.screenshot({path:join(out,'uat-1440-dark.png'),fullPage:true});report.screenshots.push('uat-1440-dark.png')
 await page.getByRole('button',{name:'新对话',exact:true}).click();await editor.fill('回放 R09：尝试禁止的 shell');await editor.press('Enter');await page.getByText('R09 受控回放已核对工具回执。',{exact:false}).waitFor({timeout:30000});pass('真实聊天显示非法工具拒绝结果')
 await page.screenshot({path:join(out,'uat-rejected.png'),fullPage:true});report.screenshots.push('uat-rejected.png')
 assert.equal((await api('/mandates')).items.length,1);assert.deepEqual(errors,[]);pass('拒绝后没有新增委托，浏览器无 pageerror')
 await writeFile(join(out,'uat-data.json'),JSON.stringify(saved,null,2));report.status='passed'
}catch(e){report.status='failed';report.error=String(e);await page.screenshot({path:join(out,'uat-failure.png'),fullPage:true});throw e}
finally{await browser.close();await writeFile(join(out,'uat-report.json'),JSON.stringify(report,null,2))}
