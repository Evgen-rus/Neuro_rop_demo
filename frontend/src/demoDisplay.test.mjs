import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  demoDealTitle,
  demoManagerName,
  displayDealTitle,
  displayEntityTitle,
  displayManagerName,
  isDemoMode,
  isDemoPersonName,
  maskCompanyBrandInText,
  maskDealTitleInText,
  maskDealTitleInValue,
  maskDemoText,
  maskManagerNameInText,
  maskPhonesInText,
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

test('DEMO_MODE keeps the last 4 phone digits and leaves other numbers alone', () => {
  const text = 'Позвонить +7 (916) 123-45-67, запасной 89161234567, короткий 916 123 45 67. Сделка 18735, дата 17.09.2026, сумма 1 500 000.'
  withDemoMode(false, () => {
    assert.equal(maskPhonesInText(text), text)
    assert.equal(maskDemoText(text), text)
  })
  withDemoMode(true, () => {
    assert.equal(
      maskPhonesInText(text),
      'Позвонить +* (***) ***-45-67, запасной *******4567, короткий *** *** 45 67. Сделка 18735, дата 17.09.2026, сумма 1 500 000.',
    )
    assert.equal(
      maskDemoText('Исходящий на +7 920 030-10-44'),
      'Исходящий на +* *** ***-10-44',
    )
    assert.equal(
      maskDemoText('Клиент +7 916 123-45-67 ждёт КП по ООО Ромашка / линия розлива.', {
        deal_id: DEAL_ID, title: REAL_TITLE,
      }),
      'Клиент +* *** ***-45-67 ждёт КП по Сделка 18735.',
    )
  })
})

test('DEMO_MODE hides a personal name after masking known manager_name', () => {
  withDemoMode(false, () => {
    assert.equal(isDemoPersonName('Александр Пахомов'), false)
  })
  withDemoMode(true, () => {
    assert.equal(isDemoPersonName('Александр Пахомов'), true)
    assert.equal(isDemoPersonName('Менеджер 42'), false)
    assert.equal(isDemoPersonName('Исходящий на +* *** ***-10-44'), false)
    assert.equal(
      maskDemoText('Александр Пахомов', { manager_id: MANAGER_ID, manager_name: 'Александр Пахомов' }),
      'Менеджер 42',
    )
  })
})

test('DEMO_MODE replaces company brand with asterisks of the same length', () => {
  const text = [
    'ООО "ПрактикМ"',
    'E-mail: 129@praktikm.ru',
    'Сайты: https://praktikm.ru и http://praktikmetiket.ru',
    'https://vk.com/praktikm1',
    'https://t.me/praktikm',
  ].join('\n')
  withDemoMode(false, () => {
    assert.equal(maskCompanyBrandInText(text), text)
    assert.equal(maskDemoText(text), text)
  })
  withDemoMode(true, () => {
    assert.equal(
      maskDemoText(text),
      [
        'ООО "********"',
        'E-mail: 129@********.ru',
        'Сайты: https://********.ru и http://********etiket.ru',
        'https://vk.com/********1',
        'https://t.me/********',
      ].join('\n'),
    )
  })
})
