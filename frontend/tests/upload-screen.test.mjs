import assert from 'node:assert/strict'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { loadSource } from './load-source.mjs'

const { UploadScreen } = await loadSource('components/UploadScreen.tsx')
const { DEFAULT_SETTINGS } = await loadSource('types.ts')
const { installFileDropHandlers } = await loadSource('fileDrop.ts')

test('an import error leaves retry and open-another-photo usable after dropping onto the rendered upload component', async () => {
  const dom = new JSDOM('<div id="root"></div>', { pretendToBeVisual: true, url: 'http://localhost' })
  const prior = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT }
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const root = createRoot(document.querySelector('#root'))
  let active = false
  let imports = 0
  let retries = 0
  let pickerOpens = 0
  const controller = installFileDropHandlers(window, {
    canDrop: () => true,
    onActiveChange: (value) => { active = value },
    onDrop: () => { imports++ },
  })
  const props = {
    settings: DEFAULT_SETTINGS,
    onSettingsChange() {},
    onBrowse() { controller.reset(); pickerOpens++ },
    onFile() { imports++ },
    onRetry() { controller.reset(); retries++ },
    onCancel() {},
    onIncomingError() {},
  }
  const dispatchDrag = (target, type) => {
    const event = new window.MouseEvent(type, { bubbles: true, cancelable: true, clientX: 150, clientY: 150 })
    Object.defineProperty(event, 'dataTransfer', { value: { types: ['Files'], items: [], files: [] } })
    target.dispatchEvent(event)
  }
  try {
    await act(async () => root.render(createElement(UploadScreen, props)))
    const prompt = document.querySelector('.upload-prompt h1')
    await act(async () => { dispatchDrag(prompt, 'dragenter'); dispatchDrag(prompt, 'drop') })
    assert.equal(imports, 1)
    assert.equal(active, false)
    await act(async () => root.render(createElement(UploadScreen, { ...props, filename: 'sky.jpg', error: '无法读取照片，请重新选择文件。' })))
    assert.match(document.querySelector('[role="alert"]').textContent, /无法读取照片/)
    const retry = [...document.querySelectorAll('button')].find((button) => button.textContent === '重新尝试')
    const browse = [...document.querySelectorAll('button')].find((button) => button.textContent === '打开其他照片')
    assert.equal(retry.disabled, false)
    assert.equal(browse.disabled, false)
    await act(async () => retry.click())
    assert.equal(retries, 1)
    assert.equal(pickerOpens, 0, 'retry must not bubble into an unwanted file picker')
    await act(async () => browse.click())
    assert.equal(pickerOpens, 1)
    assert.equal(active, false)
    assert.equal(imports, 1, 'error actions must not re-enter the drop handler')
  } finally {
    controller.dispose()
    await act(async () => root.unmount())
    dom.window.close()
    if (prior.window === undefined) delete globalThis.window; else globalThis.window = prior.window
    if (prior.document === undefined) delete globalThis.document; else globalThis.document = prior.document
    if (prior.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT; else globalThis.IS_REACT_ACT_ENVIRONMENT = prior.act
  }
})
