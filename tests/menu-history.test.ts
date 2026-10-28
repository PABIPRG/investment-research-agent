import assert from 'node:assert/strict'
import test from 'node:test'
import { MenuHistory } from '../product/ui/shell/menu-history.js'

function fixture() {
  const entries: any[] = [{ route: 'existing' }]
  let index = 0,
    backs = 0
  const changes: boolean[] = []
  const port = {
    get state() {
      return entries[index]
    },
    pushState(state: unknown) {
      entries.splice(index + 1)
      entries.push(state)
      index++
    },
    back() {
      backs++
    },
  }
  const menu = new MenuHistory(port, 'menu-1', (open) => changes.push(open))
  return {
    menu,
    port,
    entries,
    changes,
    get backs() {
      return backs
    },
    back() {
      index--
      menu.pop()
    },
    forward(eligible = true) {
      index++
      menu.pop(eligible)
    },
  }
}
test('菜单只建立一项临时历史，保留已有路由状态', () => {
  const f = fixture()
  f.menu.open()
  f.menu.open()
  assert.equal(f.entries.length, 2)
  assert.equal(f.port.state.route, 'existing')
  assert.deepEqual(f.changes, [true])
})
test('浏览器返回先关闭菜单，前进可恢复菜单', () => {
  const f = fixture()
  f.menu.open()
  f.back()
  f.forward()
  assert.deepEqual(f.changes, [true, false, true])
})
test('关闭按钮只返回一次，返回尚未完成时不能重复打开', () => {
  const f = fixture()
  f.menu.open()
  f.menu.close()
  f.menu.close()
  f.menu.open()
  assert.equal(f.backs, 1)
  assert.equal(f.entries.length, 2)
  f.back()
  f.menu.open()
  assert.deepEqual(f.changes, [true, false, true])
})
test('菜单不会回退其他功能后来建立的历史项', () => {
  const f = fixture()
  f.menu.open()
  f.port.pushState({ route: 'other' })
  f.menu.close()
  assert.equal(f.backs, 0)
  assert.equal(f.port.state.route, 'other')
})
test('桌面断点前进不会恢复隐藏菜单，缩窄后仍保持关闭', () => {
  const f = fixture()
  f.menu.open()
  f.menu.close()
  f.back()
  f.forward(false)
  assert.deepEqual(f.changes, [true, false])
  f.menu.open()
  assert.deepEqual(f.changes, [true, false, true])
})
