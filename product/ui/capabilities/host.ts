import type { Context } from '@deepseek-ai/cordis'
import '@deepseek-ai/dsh-client-connection'
import { readCapabilityCatalog } from './catalog.js'
/** DSH's authenticated transport owns access; no public endpoint or business write. */
export function installCapabilityCatalog(ctx: Context) {
  ctx.connection.fetch.register({
    path: '/api/huohuo/capabilities',
    methods: ['GET'],
    requestBody: 'buffered',
    fetch: async () => {
      const headers = { 'Cache-Control': 'no-store' }
      try {
        return Response.json(
          await readCapabilityCatalog(
            process.env.HUOHUO_CHAT_API ?? '',
            process.env.HUOHUO_USER_TOKEN ?? '',
          ),
          { headers },
        )
      } catch {
        return Response.json(
          { error: '能力目录读取失败，请重试；不会因此更改工具或权限。' },
          { status: 503, headers },
        )
      }
    },
  })
}
