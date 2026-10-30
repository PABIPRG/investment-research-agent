/** This is operator configuration, never model input or a request Host header. */
export function productOrigin(value?: string) {
  if (!value) throw new Error('当前聊天未配置可信网页入口，请使用顶部导航')
  const url = new URL(value)
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
  if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) || url.username || url.password || url.pathname !== '/' || url.search || url.hash)
    throw new Error('公开网页入口无效，请使用顶部导航')
  return url.origin
}
