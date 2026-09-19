import assert from 'node:assert/strict'
import { test } from 'node:test'
import { bitrixDealUrl } from './dealDisplay.ts'
import { isDemoMode, setDemoMode } from './demoDisplay.ts'

function withDemoMode(enabled, fn) {
  const previous = isDemoMode()
  setDemoMode(enabled)
  try {
    fn()
  } finally {
    setDemoMode(previous)
  }
}

test('DEMO_MODE does not emit a live Bitrix deal URL', () => {
  withDemoMode(false, () => {
    assert.equal(bitrixDealUrl('18735'), 'https://obtorg.bitrix24.ru/crm/deal/details/18735/')
    assert.equal(bitrixDealUrl(''), '')
  })

  withDemoMode(true, () => {
    assert.equal(bitrixDealUrl('18735'), '')
    assert.equal(bitrixDealUrl(''), '')
  })
})
