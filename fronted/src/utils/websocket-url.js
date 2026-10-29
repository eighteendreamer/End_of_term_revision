// 与 HTTP API 共用站点入口，避免线上连接到访问者的 localhost。
export function createChatWebSocketUrl(userId, token, pageLocation = window.location) {
  const protocol = pageLocation.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = new URL(`${protocol}//${pageLocation.host}/ws/${encodeURIComponent(userId)}`)
  url.searchParams.set('token', token || '')
  return url.toString()
}
