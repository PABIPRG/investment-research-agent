import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { apply } from '../product/ui/host.js'

const assets = new URL('../../product/ui/assets/', import.meta.url)
const digest = (data: Uint8Array) => createHash('sha256').update(data).digest('hex')

test('腮红外观资源指纹与实际交付文件相符，原12个动作完整保留', async () => {
  const manifest = JSON.parse(
    await readFile(new URL('companion/resource-manifest.json', assets), 'utf8'),
  )
  for (const [name, sha] of Object.entries(manifest.sha256)) {
    assert.equal(digest(await readFile(new URL(`companion/${name}`, assets))), sha, name)
  }
  for (const [name, sha] of Object.entries(manifest.brandSha256)) {
    assert.equal(digest(await readFile(new URL(name, assets))), sha, name)
  }
  const glb = await readFile(new URL('companion/huohuo-animated.glb', assets))
  const document = JSON.parse(glb.subarray(20, 20 + glb.readUInt32LE(12)).toString())
  assert.deepEqual(document.animations.map((clip: { name: string }) => clip.name).sort(), [
    'awaiting_reply',
    'cautious',
    'confused',
    'discovery',
    'gentle_knock',
    'idle',
    'listening',
    'playful',
    'relieved',
    'speaking',
    'thinking',
    'thinking_notes',
  ])
})

test('新顶部栏图标经既有Host可读取，拥有透明通道且独立于通用头像', async (t) => {
  const previous = process.env.HUOHUO_CHAT_API
  const previousToken = process.env.HUOHUO_USER_TOKEN
  process.env.HUOHUO_CHAT_API = 'http://127.0.0.1:18854'
  process.env.HUOHUO_USER_TOKEN = 'asset-route-fixture'
  t.after(() => {
    if (previous === undefined) delete process.env.HUOHUO_CHAT_API
    else process.env.HUOHUO_CHAT_API = previous
    if (previousToken === undefined) delete process.env.HUOHUO_USER_TOKEN
    else process.env.HUOHUO_USER_TOKEN = previousToken
  })
  const routes = new Map<string, { fetch: () => Promise<Response> }>()
  const indexRows: { kind: string; html?: string }[] = []
  apply({
    on: (event: string, callback: (rows: typeof indexRows) => void) => {
      if (event === 'webserver/index-inject') callback(indexRows)
    },
    connection: {
      fetch: {
        register: (route: { path: string; fetch: () => Promise<Response> }) =>
          routes.set(route.path, route),
      },
    },
  } as any)
  assert.ok(
    indexRows.some((row) => row.kind === 'html' && row.html?.includes('火火，你的投研好伙伴')),
  )
  const response = await routes.get('/api/huohuo/companion/header-peek.png')!.fetch()
  assert.equal(response.headers.get('Content-Type'), 'image/png')
  assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff')
  const png = Buffer.from(await response.arrayBuffer())
  assert.equal(png.subarray(1, 4).toString(), 'PNG')
  assert.equal(png.readUInt32BE(16), 256)
  assert.equal(png[25], 6, 'RGBA PNG')
  assert.notEqual(digest(png), digest(await readFile(new URL('brand.png', assets))))
})
