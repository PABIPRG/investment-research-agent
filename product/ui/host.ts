import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/dsh-client-connection'
import { readFile } from 'node:fs/promises'
import { createQueryBridge, queryPaths } from './bridge.js'

import { createNotificationBridge, notificationPaths } from './notification-bridge.js'
import { createInvestmentBridge, investmentPaths } from './investment-bridge.js'
import { createMandateBridge, mandatePaths } from './mandate-bridge.js'

export const inject = ['connection']
/** Mount only owner-authenticated reads on DSH's existing transport. */
export function apply(ctx: Context): void {
  const bridge = createQueryBridge(process.env.HUOHUO_CHAT_API ?? '', process.env.HUOHUO_USER_TOKEN ?? '')
  const notifications = createNotificationBridge(process.env.HUOHUO_CHAT_API ?? '', process.env.HUOHUO_USER_TOKEN ?? '')
  for (const path of notificationPaths) ctx.connection.fetch.register({ path, methods: path.endsWith('-config') ? ['GET','POST'] : ['GET'], requestBody: 'buffered', fetch: notifications })
  const mandates = createMandateBridge(process.env.HUOHUO_CHAT_API ?? '', process.env.HUOHUO_USER_TOKEN ?? '')
  const investment = createInvestmentBridge(process.env.HUOHUO_CHAT_API ?? '', process.env.HUOHUO_USER_TOKEN ?? '')
  for (const path of investmentPaths) ctx.connection.fetch.register({ path, methods: [path.endsWith('-command') ? 'POST' : 'GET'], requestBody: 'buffered', fetch: investment })
  for (const path of mandatePaths) ctx.connection.fetch.register({ path, methods: [path.endsWith('-command') ? 'POST' : 'GET'], requestBody: 'buffered', fetch: mandates })
  for (const path of queryPaths) ctx.connection.fetch.register({ path, methods: ['GET'], requestBody: 'buffered', fetch: bridge })
  for (const [name, mime] of [['brand.png', 'image/png'], ['favicon.ico', 'image/x-icon']]) {
    const asset = new URL(`../../../product/ui/assets/${name}`, import.meta.url)
    ctx.connection.fetch.register({ path: `/api/huohuo/${name}`, methods: ['GET'], requestBody: 'buffered',
      fetch: async () => new Response(new Uint8Array(await readFile(asset)), { headers: {
        'Content-Type': mime, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
      } }) })
  }
}
