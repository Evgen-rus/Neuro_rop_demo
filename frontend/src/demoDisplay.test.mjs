import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  demoDealTitle,
  demoManagerName,
  displayDealTitle,
  displayEntityTitle,
  displayManagerName,
  isDemoMode,
  maskDealTitleInText,
  maskDealTitleInValue,
  maskDemoText,
  maskManagerNameInText,
  setDemoMode,
} from './demoDisplay.ts'

const REAL_TITLE = 'ООО Ромашка / линия розлива'
const DEAL_ID = '18735'

function withDemoMode(enabled, fn) {
  const previous = isDemoMode()
  setDemoMode(enabled)
  try {
    fn()
  } finally {
    setDemoMode(previous)
  }
}

test('DEMO_MODE shows Сделка {deal_id} and leaves production titles unchanged', () => {
  withDemoMode(false, () => {
    assert.equal(displayDealTitle(DEAL_ID, REAL_TITLE), REAL_TITLE)
    assert.equal(displayDealTitle(DEAL_ID, ''), `Сделка #${DEAL_ID}`)
    assert.equal(displayDealTitle(DEAL_ID, '   ', ''), '')
    assert.equal(displayEntityTitle('deal', DEAL_ID, REAL_TITLE), REAL_TITLE)
    assert.equal(displayEntityTitle('lead', '88', 'Лид Ромашка'), 'Лид Ромашка')
  })

  withDemoMode(true, () => {
    assert.equal(demoDealTitle(DEAL_ID), 'Сделка 18735')
    assert.equal(displayDealTitle(DEAL_ID, REAL_TITLE), 'Сделка 18735')
    assert.equal(displayDealTitle(DEAL_ID, ''), 'Сделка 18735')
    assert.equal(displayDealTitle(DEAL_ID, REAL_TITLE, REAL_TITLE), 'Сделка 18735')
    assert.equal(displayEntityTitle('deal', DEAL_ID, REAL_TITLE), 'Сделка 18735')
    assert.equal(displayEntityTitle('lead', '88', 'Лид Ромашка'), 'Лид Ромашка')
  })
})

test('DEMO_MODE replaces the exact current deal.title in rendered text only', () => {
  const markdown = `# ${REAL_TITLE}\n\nРекомендация: позвонить по ${REAL_TITLE}.\nСоседняя сделка ООО Ромашка остаётся.`
  withDemoMode(false, () => {
    assert.equal(maskDealTitleInText(markdown, DEAL_ID, REAL_TITLE), markdown)
    assert.deepEqual(
      maskDealTitleInValue({ title: REAL_TITLE, deal_id: DEAL_ID }, DEAL_ID, REAL_TITLE),
      { title: REAL_TITLE, deal_id: DEAL_ID },
    )
  })

  withDemoMode(true, () => {
    assert.equal(
      maskDealTitleInText(markdown, DEAL_ID, REAL_TITLE),
      '# Сделка 18735\n\nРекомендация: позвонить по Сделка 18735.\nСоседняя сделка ООО Ромашка остаётся.',
    )
    assert.equal(maskDealTitleInText(markdown, DEAL_ID, ''), markdown)
    const masked = maskDealTitleInValue(
      { title: REAL_TITLE, deal_id: DEAL_ID, note: `Контекст ${REAL_TITLE}` },
      DEAL_ID,
      REAL_TITLE,
    )
    assert.equal(masked.title, 'Сделка 18735')
    assert.equal(masked.deal_id, DEAL_ID)
    assert.equal(masked.note, 'Контекст Сделка 18735')
  })
})

const REAL_MANAGER = 'Иванов Иван'
const MANAGER_ID = '42'

test('DEMO_MODE shows Менеджер {manager_id} and leaves production names unchanged', () => {
  withDemoMode(false, () => {
    assert.equal(displayManagerName(MANAGER_ID, REAL_MANAGER), REAL_MANAGER)
    assert.equal(displayManagerName(MANAGER_ID, ''), `Ответственный #${MANAGER_ID}`)
    assert.equal(displayManagerName(MANAGER_ID, '   ', 'Не назначен'), 'Не назначен')
  })

  withDemoMode(true, () => {
    assert.equal(demoManagerName(MANAGER_ID), 'Менеджер 42')
    assert.equal(displayManagerName(MANAGER_ID, REAL_MANAGER), 'Менеджер 42')
    assert.equal(displayManagerName(MANAGER_ID, ''), 'Менеджер 42')
    assert.equal(displayManagerName('', REAL_MANAGER), 'Менеджер')
  })
})

test('DEMO_MODE replaces the exact current manager_name in rendered text only', () => {
  const markdown = `${REAL_MANAGER} ведёт ${REAL_TITLE}. Коллега Иванов остаётся.`
  withDemoMode(false, () => {
    assert.equal(maskManagerNameInText(markdown, MANAGER_ID, REAL_MANAGER), markdown)
    assert.equal(maskDemoText(markdown, {
      deal_id: DEAL_ID, title: REAL_TITLE, manager_id: MANAGER_ID, manager_name: REAL_MANAGER,
    }), markdown)
  })

  withDemoMode(true, () => {
    assert.equal(
      maskManagerNameInText(markdown, MANAGER_ID, REAL_MANAGER),
      'Менеджер 42 ведёт ООО Ромашка / линия розлива. Коллега Иванов остаётся.',
    )
    assert.equal(
      maskDemoText(markdown, {
        deal_id: DEAL_ID, title: REAL_TITLE, manager_id: MANAGER_ID, manager_name: REAL_MANAGER,
      }),
      'Менеджер 42 ведёт Сделка 18735. Коллега Иванов остаётся.',
    )
    assert.equal(maskManagerNameInText(markdown, MANAGER_ID, ''), markdown)
  })
})
