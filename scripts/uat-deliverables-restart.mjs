// 由同一任务保存 baseline 后，停止/重启同一受控实例，再执行本脚本。
import assert from 'node:assert/strict'
import {readFile,writeFile,stat} from 'node:fs/promises'
import {join,resolve} from 'node:path'
import {createHash} from 'node:crypto'
const out=resolve(process.env.HUOHUO_SMOKE_OUT??'artifacts/deliverables-uat')
const runtime=JSON.parse(await readFile(join(out,'runtime.json'),'utf8'))
const baseline=JSON.parse(await readFile(join(out,'restart-baseline.json'),'utf8'))
assert.equal(runtime.instance,baseline.instance,'必须验证原受控实例，不得改为新数据')
// 前一轮成功下载记录也可作字节基线，但必须确实早于本次服务启动。
const previous=JSON.parse(await readFile(join(out,'uat-report.json'),'utf8'))
assert.equal(previous.status,'passed')
assert.ok((await stat(join(out,'uat-report.json'))).mtimeMs < (await stat(join(out,'runtime.json'))).mtimeMs,'下载记录必须早于本次重启')
const {chromium}=await import(process.env.HUOHUO_PLAYWRIGHT??'playwright')
const browser=await chromium.launch({headless:true,channel:'chrome'})
const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true})
const page=await context.newPage(),report={status:'not-tested',checks:[],model:'controlled',source:'synthetic'}
try{
 await page.goto(runtime.launchUrl)
 const intro=page.getByRole('button',{name:'继续',exact:true})
 await intro.or(page.locator('[contenteditable=true]').first()).first().waitFor({timeout:30000})
 if(await intro.isVisible())await intro.click()
 await page.locator('[contenteditable=true]').first().waitFor();await page.waitForTimeout(1000)
 for(const file of baseline.files){
  const response=await context.request.get(`http://127.0.0.1:${runtime.web}/api/huohuo/deliverables/download?id=${file.id}&part=file`)
  assert.equal(response.status(),200)
  assert.equal(createHash('sha256').update(await response.body()).digest('hex'),file.sha256)
 }
 report.checks.push({name:`重启后 ${baseline.files.length} 份既有文件通过认证下载，SHA256 均不变`,status:'passed'})
 await page.getByRole('button',{name:'历史对话',exact:true}).click()
 await page.getByRole('dialog').locator('li button').filter({hasText:'成果受控验收'}).first().click()
 const card=page.locator('[data-presented-file]').filter({hasText:/\.xlsx/}).last();await card.waitFor({timeout:15000})
 const pending=page.waitForEvent('download');await card.getByRole('button',{name:'下载',exact:true}).click();const download=await pending
 const file=baseline.files.find(f=>f.filename===download.suggestedFilename())??previous.files.find(f=>f.name===download.suggestedFilename());assert.ok(file)
 const stream=await download.createReadStream();const blocks=[];for await(const block of stream)blocks.push(block)
 assert.equal(createHash('sha256').update(Buffer.concat(blocks)).digest('hex'),file.sha256)
 report.checks.push({name:'重启后通过真实历史对话卡片下载原 Excel，内容不变',status:'passed'})
 await page.waitForFunction(()=>!document.querySelector('[data-huohuo-conversation]')?.hasAttribute('data-history-transition'))
 await page.screenshot({path:join(out,'uat-after-restart.png'),fullPage:true});report.status='passed'
}catch(error){report.status='failed';report.error=String(error);throw error}
finally{await browser.close();await writeFile(join(out,'restart-report.json'),JSON.stringify(report,null,2))}
