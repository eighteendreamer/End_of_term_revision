import test from 'node:test'
import assert from 'node:assert/strict'
import { createChatWebSocketUrl } from '../src/utils/websocket-url.js'

test('HTTPS 页面使用当前域名的 WSS 入口', () => {
  assert.equal(
    createChatWebSocketUrl(42, 'jwt.token', { protocol: 'https:', host: 'endreversion.pantoria.cn' }),
    'wss://endreversion.pantoria.cn/ws/42?token=jwt.token'
  )
})

test('本地开发使用 WS 并保留 Vite 端口', () => {
  assert.equal(
    createChatWebSocketUrl(42, '', { protocol: 'http:', host: 'localhost:3001' }),
    'ws://localhost:3001/ws/42?token='
  )
})

test('保留非标准 HTTPS 端口与 IPv6 地址', () => {
  const url = new URL(createChatWebSocketUrl(1, null, { protocol: 'https:', host: '[::1]:8443' }))
  assert.equal(url.host, '[::1]:8443')
  assert.equal(url.protocol, 'wss:')
  assert.equal(url.searchParams.get('token'), '')
})

test('令牌中的特殊字符不会破坏查询参数', () => {
  const token = 'a+/=&?# b'
  const url = new URL(createChatWebSocketUrl(1, token, { protocol: 'https:', host: 'example.com' }))
  assert.equal(url.searchParams.get('token'), token)
  assert.equal([...url.searchParams].length, 1)
})

test('用户 ID 不会插入额外路径或查询参数', () => {
  const url = new URL(createChatWebSocketUrl('1/2?x=3', 'token', { protocol: 'https:', host: 'example.com' }))
  assert.equal(url.pathname, '/ws/1%2F2%3Fx%3D3')
  assert.equal(url.searchParams.get('x'), null)
})
