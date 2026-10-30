// 先以 --serve --business --activity 启动 smoke-skills；合成模型，零业务写入。
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { resolve, join } from 'node:path'
const out = resolve(process.env.HUOHUO_SMOKE_OUT ?? 'artifacts/question-overflow-uat')
const runtime = JSON.parse(await readFile(join(out, 'runtime.json'), 'utf8'))
const { chromium } = await import(process.env.HUOHUO_PLAYWRIGHT ?? 'playwright')
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', e => errors.push(e.message))
const report = { status: 'not-tested', model: 'controlled', data: 'synthetic', checks: [] }
const card = () => page.locator('[data-question-key] > section')
const submit = () => card().getByRole('button', { name: /提交/ })
async function operable(locator) {
  await locator.waitFor()
  const result = await locator.evaluate(el => {
    const r = el.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2
    const hit = document.elementFromPoint(x, y)
    return { visible: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
      hit: hit === el || el.contains(hit), bounds: { top: r.top, bottom: r.bottom } }
  })
  assert.ok(result.visible && result.hit, `操作被裁切或遮挡：${JSON.stringify(result)}`)
}
async function replay(id) {
  await page.getByRole('button', { name: '新对话', exact: true }).click()
  await page.locator('[data-huohuo-conversation][data-arrival="true"]').waitFor()
  const editor = page.locator('[contenteditable="true"]').first()
  await editor.fill(`回放 ${id}：合成长文本确认验收，不创建委托。`)
  await editor.press('Enter')
  await card().waitFor({ timeout: 30000 })
}
try {
  await page.goto(runtime.launchUrl)
  const next = page.getByRole('button', { name: '继续', exact: true })
  await page.locator('[data-huohuo-conversation]').waitFor({ timeout: 30000 })
  if (await next.isVisible()) await next.click()
  await replay('B17')
  await page.screenshot({ path: join(out, 'after-desktop.png') })
  if (process.env.HUOHUO_BASELINE === '1') {
    await page.screenshot({ path: join(out, 'before.png'), fullPage: true })
    await operable(submit()) // 修复前必须失败；不能用 Playwright 自动滚入代替可见性断言。
  }
  for (const colorScheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme })
    for (const [width, height] of [[1440, 900], [1024, 768], [768, 900], [390, 844], [1024, 500], [390, 500]]) {
      await page.setViewportSize({ width, height })
      await operable(submit())
      await operable(card().getByRole('radio', { name: '确认执行', exact: true }))
      await operable(card().getByRole('button', { name: '收起问题卡片', exact: true }))
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
      const heading = card().locator('.Mbwy4a_headingBlock')
      const scrollable = await heading.evaluate(el => el.scrollHeight > el.clientHeight)
      assert.ok(scrollable, '全文应可滚动')
      await heading.hover(); await page.mouse.wheel(0, 5000)
      await page.waitForFunction(() => {
        const el = document.querySelector('[data-question-key] .Mbwy4a_headingBlock')
        return el && el.scrollTop > 0
      })
      await operable(submit())
      await page.screenshot({ path: join(out, `${width}-${height}-${colorScheme}.png`) })
      await heading.evaluate(el => { el.scrollTop = 0 })
      console.log(`passed: ${width}x${height} ${colorScheme}`)
      report.checks.push({ viewport: `${width}x${height}`, colorScheme, status: 'passed' })
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  const fullText = card().getByRole('region', { name: '问题全文' })
  await fullText.evaluate(el => { el.scrollTop = 0 })
  await fullText.focus(); await page.keyboard.press('PageDown')
  await page.waitForFunction(() => document.activeElement?.scrollTop > 0)
  report.checks.push({ name: '键盘聚焦全文并 PageDown 滚动', status: 'passed' })
  await card().getByRole('button', { name: '收起问题卡片', exact: true }).click()
  await card().getByRole('button', { name: '展开问题卡片', exact: true }).click()
  await operable(submit())
  await page.reload()
  await page.getByRole('button', { name: '历史对话', exact: true }).click()
  await page.getByRole('dialog', { name: '历史对话' }).locator('li button').filter({ hasNot: page.getByText('新对话', { exact: true }) }).first().click()
  await card().waitFor({ timeout: 30000 }); await operable(submit())
  await card().getByRole('radio', { name: '确认执行', exact: true }).click()
  await submit().click()
  await page.getByText(/B17 长文本验收完成/).last().waitFor({ timeout: 30000 })
  assert.match(await page.locator('body').innerText(), /确认执行/)
  report.checks.push({ name: '收起展开、刷新恢复、鼠标确认及原生回答回执', status: 'passed' })
  await replay('B17')
  await card().getByRole('radio', { name: '取消', exact: true }).click()
  await submit().focus(); await page.keyboard.press('Enter')
  await page.getByText(/B17 长文本验收完成/).last().waitFor({ timeout: 30000 })
  assert.match(await page.locator('body').innerText(), /取消/)
  report.checks.push({ name: '取消选项及键盘 Enter 返回原生回答', status: 'passed' })
  await replay('B16')
  await operable(card().locator('.Mbwy4a_footerActions > button:last-child'))
  await card().getByRole('radio').first().click()
  await card().getByRole('checkbox').first().waitFor()
  await card().getByRole('checkbox').first().click(); await submit().click()
  await page.getByText(/B16 问答样式验收完成/).last().waitFor({ timeout: 30000 })
  report.checks.push({ name: '短问题、多题与多选回归', status: 'passed' })
  assert.deepEqual(errors, [])
  report.status = 'passed'
} catch (e) {
  report.status = 'failed'; report.error = String(e)
  await page.screenshot({ path: join(out, 'failure.png'), fullPage: true })
  throw e
} finally {
  await writeFile(join(out, process.env.HUOHUO_BASELINE === '1' ? 'baseline-report.json' : 'uat-report.json'), JSON.stringify(report, null, 2))
  await browser.close()
}
