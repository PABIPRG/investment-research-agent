import { createTransferBridge, transferPath } from './transfer-bridge.js'
import { createPersonalizationBridge, personalizationPath } from './personalization/bridge.js'
import { createDataSourceBridge, dataSourcePaths } from './data-sources/bridge.js'
import { createStrategyBridge, strategyPaths } from './strategies/bridge.js'
import { installCapabilityCatalog } from './capabilities/host.js'
import { createDeliverableDownload, deliverableDownloadPath } from './deliverables/bridge.js'
import '@deepseek-ai/dsh-session-query'
import { SessionId, SessionSeq } from '@deepseek-ai/dsh-session'
import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/dsh-client-connection'
import '@deepseek-ai/dsh-host-webserver'
import { bootInjections } from './boot.js'
import { readFile } from 'node:fs/promises'
import { createQueryBridge, queryPaths } from './bridge.js'

import { createInvestmentBridge, investmentPaths } from './investment-bridge.js'
import { createMandateBridge, mandatePaths } from './mandate-bridge.js'
import { createNotificationBridge, notificationPaths } from './notification-bridge.js'

import { createSecurityBridge, securityPath } from './security-bridge.js'

export const inject = ['connection', 'sessionQuery']
/** Mount only owner-authenticated reads on DSH's existing transport. */
export function apply(ctx: Context): void {
  ctx.connection.fetch.register({
    path: deliverableDownloadPath,
    methods: ['GET'],
    requestBody: 'buffered',
    fetch: createDeliverableDownload(
      process.env.HUOHUO_CHAT_API ?? '',
      process.env.HUOHUO_USER_TOKEN ?? '',
      async (sessionId, seq, index, signal) => {
        const { target } = await ctx.sessionQuery.readEvent(
          { sessionId: SessionId(sessionId), seq: SessionSeq(seq), before: 0, after: 0 },
          signal,
        )
        if (target.type !== 'deliverables/presented') return undefined
        const data = target.data as { files?: { path?: unknown }[] }
        const path = data.files?.[index]?.path
        return typeof path === 'string' ? path : undefined
      },
    ),
  })
  ctx.connection.fetch.register({
    path: personalizationPath,
    methods: ['POST'],
    requestBody: 'buffered',
    fetch: createPersonalizationBridge(
      process.env.HUOHUO_CHAT_API ?? '',
      process.env.HUOHUO_USER_TOKEN ?? '',
    ),
  })
  ctx.on('webserver/index-inject', (rows) => rows.push(...bootInjections()))
  installCapabilityCatalog(ctx)
  ctx.connection.fetch.register({
    path: transferPath,
    methods: ['POST'],
    requestBody: 'buffered',
    fetch: createTransferBridge(
      process.env.HUOHUO_CHAT_API ?? '',
      process.env.HUOHUO_USER_TOKEN ?? '',
    ),
  })
  const dataSources = createDataSourceBridge(
    process.env.HUOHUO_CHAT_API ?? '',
    process.env.HUOHUO_USER_TOKEN ?? '',
  )
  for (const path of dataSourcePaths)
    ctx.connection.fetch.register({
      path,
      methods: [path.endsWith('command') ? 'POST' : 'GET'],
      requestBody: 'buffered',
      fetch: dataSources,
    })
  const strategy = createStrategyBridge(
    process.env.HUOHUO_CHAT_API ?? '',
    process.env.HUOHUO_USER_TOKEN ?? '',
  )
  for (const path of strategyPaths)
    ctx.connection.fetch.register({
      path,
      methods: [path.endsWith('command') ? 'POST' : 'GET'],
      requestBody: 'buffered',
      fetch: strategy,
    })
  ctx.connection.fetch.register({
    path: securityPath,
    methods: ['POST'],
    requestBody: 'buffered',
    fetch: createSecurityBridge(
      process.env.HUOHUO_CHAT_API ?? '',
      process.env.HUOHUO_USER_TOKEN ?? '',
    ),
  })
  ctx.connection.fetch.register({
    path: '/api/huohuo/environment',
    methods: ['GET'],
    requestBody: 'buffered',
    fetch: async () =>
      Response.json(
        { controlled: Boolean(process.env.HUOHUO_SKILLS_PROOF) },
        { headers: { 'Cache-Control': 'no-store' } },
      ),
  })
  const bridge = createQueryBridge(
    process.env.HUOHUO_CHAT_API ?? '',
    process.env.HUOHUO_USER_TOKEN ?? '',
  )
  const notifications = createNotificationBridge(
    process.env.HUOHUO_CHAT_API ?? '',
    process.env.HUOHUO_USER_TOKEN ?? '',
  )
  for (const path of notificationPaths)
    ctx.connection.fetch.register({
      path,
      methods: path.endsWith('-config')
        ? ['GET', 'POST']
        : path.endsWith('-command')
          ? ['POST']
          : ['GET'],
      requestBody: 'buffered',
      fetch: notifications,
    })
  const mandates = createMandateBridge(
    process.env.HUOHUO_CHAT_API ?? '',
    process.env.HUOHUO_USER_TOKEN ?? '',
  )
  const investment = createInvestmentBridge(
    process.env.HUOHUO_CHAT_API ?? '',
    process.env.HUOHUO_USER_TOKEN ?? '',
  )
  for (const path of investmentPaths)
    ctx.connection.fetch.register({
      path,
      methods: [path.endsWith('-command') ? 'POST' : 'GET'],
      requestBody: 'buffered',
      fetch: investment,
    })
  for (const path of mandatePaths)
    ctx.connection.fetch.register({
      path,
      methods: [path.endsWith('-command') ? 'POST' : 'GET'],
      requestBody: 'buffered',
      fetch: mandates,
    })
  for (const path of queryPaths)
    ctx.connection.fetch.register({
      path,
      methods: ['GET'],
      requestBody: 'buffered',
      fetch: bridge,
    })
  for (const [name, mime] of [
    ['brand.png', 'image/png'],
    ['favicon.ico', 'image/x-icon'],
    ['companion/fallback.png', 'image/png'],
    ['companion/header-peek.png', 'image/png'],
    ['companion/huohuo-animated.glb', 'model/gltf-binary'],
    ...[
      'renderer.js',
      'vendor/three.module.js',
      'vendor/three.core.js',
      'vendor/GLTFLoader.js',
      'vendor/BufferGeometryUtils.js',
      'vendor/RoomEnvironment.js',
    ].map((name) => [`companion/${name}`, 'text/javascript']),
  ]) {
    const asset = new URL(`../../../product/ui/assets/${name}`, import.meta.url)
    ctx.connection.fetch.register({
      path: `/api/huohuo/${name}`,
      methods: ['GET'],
      requestBody: 'buffered',
      fetch: async () =>
        new Response(new Uint8Array(await readFile(asset)), {
          headers: {
            'Content-Type': mime,
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
          },
        }),
    })
  }
}
