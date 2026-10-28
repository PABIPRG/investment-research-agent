import test from 'node:test'
import assert from 'node:assert/strict'
import { readCapabilityCatalog } from '../product/ui/capabilities/catalog.js'
import { allowedChatToolNames } from '../product/chat/tools.js'
import { chatSkillNames } from '../product/chat/policy.js'

test('能力目录使用当前装配和允许名单，不包含未整合工具或凭据', async () => {
  const data = await readCapabilityCatalog('http://127.0.0.1:18840', 'test-private-token')
  assert.deepEqual(
    data.items
      .filter((x) => x.kind === 'tool')
      .map((x) => x.id)
      .sort(),
    [...allowedChatToolNames].sort(),
  )
  assert.deepEqual(
    data.items
      .filter((x) => x.kind === 'skill')
      .map((x) => x.id)
      .sort(),
    [...chatSkillNames].sort(),
  )
  assert.equal(
    data.items.some((x) => x.id === 'commit_investment_change'),
    true,
  )
  assert.equal(JSON.stringify(data).includes('test-private-token'), false)
  assert.equal(JSON.stringify(data).includes('/private/'), false)
})
test('限制不伪装成待授权或可用，目录读取不执行工具', async () => {
  const old = globalThis.fetch
  globalThis.fetch = async () => {
    throw Error('目录不得探测数据源')
  }
  try {
    const data = await readCapabilityCatalog('http://127.0.0.1:18840', 'fixture')
    assert.equal(data.items.some((x) => x.id === 'portfolio_lookup'), false)
    assert.equal(data.items.some((x) => x.id === 'portfolio_risk_analysis'), false)
    assert.equal(data.items.some((x) => x.id === 'watchlist_lookup'), false)
    assert.equal(data.items.find((x) => x.id === 'commit_investment_change')?.action, 'investment')
    assert.equal(data.items.find((x) => x.id === 'strategy_pool_lookup')?.status, 'registered')
    assert.equal(data.items.find((x) => x.id === 'read_investment_facts')?.status, 'registered')
    assert.equal(
      data.items.find((x) => x.id === 'huohuo-investment-facts')?.title,
      '投资事实与用户记录',
    )
    assert.ok(data.items.every((x) => x.title && x.description && x.source && x.note))
  } finally {
    globalThis.fetch = old
  }
})

test('搜索同时匹配中文与内部名称，并与类型/状态筛选组合', async () => {
  const { filterCapabilities } = await import('../product/ui/capabilities/model.js')
  const { items } = await readCapabilityCatalog('http://127.0.0.1:18840', 'fixture')
  assert.deepEqual(
    filterCapabilities(items, 'preview_investment_change 投资', 'tool', 'registered')
      .map((x) => x.id)
      .sort(),
    ['preview_investment_change'],
  )
  assert.equal(
    filterCapabilities(items, '投资', 'skill', 'registered').some(
      (x) => x.id === 'huohuo-investment-facts',
    ),
    true,
  )
  assert.equal(filterCapabilities(items, '不可能匹配的名称', 'all', 'all').length, 0)
  assert.equal(filterCapabilities(items, '  ', 'all', 'all').length, items.length)
})

test('目录端点只声明GET，失败不暴露配置或异常', async (t) => {
  const { installCapabilityCatalog } = await import('../product/ui/capabilities/host.js')
  const previous = process.env.HUOHUO_CHAT_API
  const previousToken = process.env.HUOHUO_USER_TOKEN
  process.env.HUOHUO_CHAT_API = 'https://invalid.example'
  process.env.HUOHUO_USER_TOKEN = 'never-leak'
  t.after(() => {
    if (previous === undefined) delete process.env.HUOHUO_CHAT_API
    else process.env.HUOHUO_CHAT_API = previous
    if (previousToken === undefined) delete process.env.HUOHUO_USER_TOKEN
    else process.env.HUOHUO_USER_TOKEN = previousToken
  })
  let route: any
  installCapabilityCatalog({
    connection: {
      fetch: {
        register: (value: any) => {
          route = value
        },
      },
    },
  } as any)
  assert.deepEqual(route.methods, ['GET'])
  const response = await route.fetch()
  assert.equal(response.status, 503)
  assert.equal(response.headers.get('Cache-Control'), 'no-store')
  const body = await response.text()
  assert.equal(body.includes('never-leak'), false)
  assert.equal(body.includes('invalid.example'), false)
})
