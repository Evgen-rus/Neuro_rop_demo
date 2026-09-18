import assert from 'node:assert/strict'
import { test } from 'node:test'
import { businessNow, moscowDateInputValue, setBusinessNow } from './dateTime.ts'

test('business clock uses backend reference time for today', () => {
  setBusinessNow('2026-09-18T18:00:00+03:00')
  try {
    assert.equal(moscowDateInputValue(), '2026-09-18')
    const current = businessNow()
    assert.equal(current.toISOString(), new Date('2026-09-18T18:00:00+03:00').toISOString())
  } finally {
    setBusinessNow(null)
  }
})
