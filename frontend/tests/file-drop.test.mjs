import assert from 'node:assert/strict'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { loadSource } from './load-source.mjs'

const { installFileDropHandlers } = await loadSource('fileDrop.ts')
const { firstSupportedFileFromTransfer } = await loadSource('incomingFile.ts')

function transfer(files = [new File(['photo'], 'sky.jpg', { type: 'image/jpeg' })]) {
  return { types: ['Files'], items: files.map((file) => ({ kind: 'file', getAsFile: () => file })), files, dropEffect: 'none' }
}

function fixture(t, overrides = {}) {
  const dom = new JSDOM('<main><div id="zone"><span id="child">Drop here</span></div><button>Open another photo</button></main>', { pretendToBeVisual: true })
  const { window } = dom
  const states = []
  const drops = []
  let active = false
  let now = 0
  let nextTimer = 1
  const timers = new Map()
  window.setTimeout = (fn, delay) => { const id = nextTimer++; timers.set(id, { fn, due: now + delay }); return id }
  window.clearTimeout = (id) => timers.delete(id)
  const callbacks = {
    canDrop: () => true,
    ...overrides,
    onActiveChange(value) { active = value; states.push(value); overrides.onActiveChange?.(value) },
    onDrop(data) { drops.push({ data, active }); overrides.onDrop?.(data) },
  }
  const controller = installFileDropHandlers(window, callbacks)
  const child = window.document.querySelector('#child')
  function drag(type, data = transfer(), target = child, coordinates = {}) {
    const event = new window.MouseEvent(type, { bubbles: true, cancelable: true, clientX: 100, clientY: 100, ...coordinates })
    Object.defineProperty(event, 'dataTransfer', { value: data })
    target.dispatchEvent(event)
    return event
  }
  function tick(milliseconds) {
    now += milliseconds
    for (const [id, timer] of [...timers]) {
      if (timer.due <= now) { timers.delete(id); timer.fn() }
    }
  }
  t.after(() => { controller.dispose(); dom.window.close() })
  return { window, child, drag, tick, controller, callbacks, states, drops, timers, get active() { return active } }
}

test('nested photo drop clears the banner before import and is handled exactly once despite a child drop handler', (t) => {
  const f = fixture(t)
  let childDrops = 0
  f.child.addEventListener('drop', (event) => { event.stopPropagation(); childDrops++ })
  const data = transfer()
  f.drag('dragenter', data)
  assert.equal(f.active, true)
  const event = f.drag('drop', data)
  assert.equal(event.defaultPrevented, true)
  assert.deepEqual(f.states, [true, false])
  assert.deepEqual(f.drops, [{ data, active: false }])
  assert.equal(childDrops, 0, 'the capture owner prevents a duplicate child import')
  assert.equal(f.timers.size, 0)
})

test('nested enter/leave does not flicker; leaving the window clears the banner', (t) => {
  const f = fixture(t)
  f.drag('dragenter', transfer(), f.child.parentElement)
  f.drag('dragenter')
  f.drag('dragleave')
  assert.equal(f.active, true)
  f.drag('dragleave', null, f.child, { clientX: -1 })
  assert.equal(f.active, false)
  f.drag('dragover')
  assert.equal(f.active, true, 'dragover can recover from a missing dragenter')
  f.drag('dragleave', null, f.child, { clientX: f.window.innerWidth })
  assert.equal(f.active, false)
})

for (const eventName of ['dragend', 'blur', 'focus', 'pointerdown', 'Escape', 'visibilitychange']) {
  test(`${eventName} ends a canceled or interrupted external drag`, (t) => {
    const f = fixture(t)
    f.drag('dragenter')
    if (eventName === 'Escape') {
      f.child.dispatchEvent(new f.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    } else if (eventName === 'visibilitychange') {
      Object.defineProperty(f.window.document, 'hidden', { configurable: true, value: true })
      f.window.document.dispatchEvent(new f.window.Event('visibilitychange'))
    } else {
      f.window.dispatchEvent(new f.window.Event(eventName))
    }
    assert.equal(f.active, false)
    assert.equal(f.timers.size, 0)
    assert.equal(f.drops.length, 0)
  })
}

test('missed native cancellation events cannot leave the banner behind; live dragover keeps it active', (t) => {
  const f = fixture(t)
  f.drag('dragenter')
  f.tick(1000)
  f.drag('dragover')
  f.tick(1000)
  assert.equal(f.active, true)
  f.tick(600)
  assert.equal(f.active, false)
  assert.equal(f.drops.length, 0)
  assert.equal(f.timers.size, 0)
})

test('text/URL drags retain native interaction and never start photo import', (t) => {
  const f = fixture(t)
  const textData = { types: ['text/plain'], items: [{ kind: 'string' }], files: [] }
  for (const name of ['dragenter', 'dragover', 'drop']) assert.equal(f.drag(name, textData).defaultPrevented, false)
  assert.equal(f.active, false)
  assert.equal(f.drops.length, 0)
})

test('busy state suppresses the banner and passes one drop to the busy-state explanation', (t) => {
  const f = fixture(t, { canDrop: () => false })
  const data = transfer()
  f.drag('dragenter', data)
  f.drag('dragover', data)
  assert.equal(data.dropEffect, 'none')
  assert.equal(f.active, false)
  f.drag('drop', data)
  assert.equal(f.drops.length, 1)
  assert.equal(f.active, false)
})

test('file transfer is snapshotted synchronously before the browser protects its drop data store', async (t) => {
  let pending
  const f = fixture(t, { onDrop: (data) => { pending = firstSupportedFileFromTransfer(data) } })
  const file = new File(['photo'], 'snapshot.jpg', { type: 'image/jpeg' })
  const data = transfer([file])
  f.drag('drop', data)
  data.files.length = 0
  data.items.length = 0
  data.types.length = 0
  assert.equal(await pending, file)
  assert.equal(f.drops.length, 1)
})

test('unsupported/unreadable incoming data does not strand the banner or prevent the next import', async (t) => {
  const imports = []
  const errors = []
  const jobs = []
  const f = fixture(t, { onDrop: (data) => {
    jobs.push(firstSupportedFileFromTransfer(data).then((file) => { if (file) imports.push(file); else errors.push('unsupported') }).catch((error) => errors.push(error.message)))
  } })
  const unreadable = { name: 'attachment', size: 10, type: '', lastModified: 1, slice() { throw new Error('native drag data unavailable') } }
  for (const file of [new File(['unknown'], 'attachment.bin'), unreadable]) {
    f.drag('dragenter')
    f.drag('drop', transfer([file]))
    assert.equal(f.active, false)
    await jobs.at(-1)
  }
  f.controller.reset() // Same reset used by the Open photo / retry path.
  const photo = new File(['photo'], 'retry.jpg', { type: 'image/jpeg' })
  f.drag('dragenter')
  f.drag('drop', transfer([photo]))
  await jobs.at(-1)
  assert.equal(errors.length, 2)
  assert.deepEqual(imports, [photo])
  assert.equal(f.active, false)
})

test('dispose cancels the fallback and removes listeners before a remount', (t) => {
  const f = fixture(t)
  f.drag('dragenter')
  f.controller.dispose()
  f.tick(2000)
  f.drag('drop')
  assert.equal(f.drops.length, 0)
  assert.equal(f.timers.size, 0)
  const next = installFileDropHandlers(f.window, f.callbacks)
  f.drag('dragenter')
  f.drag('drop')
  assert.equal(f.drops.length, 1)
  assert.equal(f.active, false)
  next.dispose()
})
