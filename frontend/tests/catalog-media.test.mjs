import assert from 'node:assert/strict'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { loadSource } from './load-source.mjs'

const { ResultSidebar } = await loadSource('components/ResultSidebar.tsx')
const { DEFAULT_SETTINGS } = await loadSource('types.ts')

test('DSO catalogue shows its real reference image and opens the selected picture before the long table', async () => {
  const dom = new JSDOM('<div id="root"></div>', { pretendToBeVisual: true, url: 'http://localhost' })
  const prior = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT, observer: globalThis.IntersectionObserver }
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  globalThis.IntersectionObserver = class { observe() {} disconnect() {} }
  const root = createRoot(document.querySelector('#root'))
  const mapped = { id: 'M31', name: 'M31', label: 'M31 仙女座星系', category: 'deepSky', type: '星系', magnitude: 3.4, thumbnail: '/media/m31-nasa.jpg', imageCredit: 'NASA / ESA', sourceUrl: 'https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubble-messier-catalog/messier-31/' }
  const unknown = { id: 'NGC6269', name: 'NGC6269', label: 'NGC6269', category: 'deepSky', type: '星系', magnitude: 12.6 }
  const props = { result: { metadata: { filename: 'sky.jpg' }, wcs: {}, objects: [mapped, unknown], raw: {} }, settings: DEFAULT_SETTINGS, selectedId: mapped.id, onSettingsChange() {}, onApplySettings() {}, onSelect() {}, onOpenSkyMap() {} }
  try {
    await act(async () => root.render(createElement(ResultSidebar, props)))
    const table = document.querySelector('.catalog-table')
    const detail = document.querySelector('.catalog-detail')
    assert.ok(detail.compareDocumentPosition(table) & window.Node.DOCUMENT_POSITION_FOLLOWING)
    assert.equal(detail.querySelector('img').getAttribute('src'), mapped.thumbnail)
    assert.equal(table.querySelectorAll('.catalog-image-cell img').length, 1)
    assert.equal(table.querySelector('.catalog-image-cell img').getAttribute('src'), mapped.thumbnail)
    assert.match(table.querySelector('.catalog-image-placeholder').textContent, /查找.*配图/)
    assert.ok(detail.querySelector('a').href.startsWith('https://science.nasa.gov/'))
  } finally {
    await act(async () => root.unmount())
    dom.window.close()
    if (prior.window === undefined) delete globalThis.window; else globalThis.window = prior.window
    if (prior.document === undefined) delete globalThis.document; else globalThis.document = prior.document
    if (prior.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT; else globalThis.IS_REACT_ACT_ENVIRONMENT = prior.act
    if (prior.observer === undefined) delete globalThis.IntersectionObserver; else globalThis.IntersectionObserver = prior.observer
  }
})

test('missing DSO pictures load only when visible, share selected-detail requests, and retry a failed archive lookup', async () => {
  const dom = new JSDOM('<div id="root"></div>', { pretendToBeVisual: true, url: 'http://localhost' })
  const prior = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT, observer: globalThis.IntersectionObserver, fetch: globalThis.fetch }
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const observers = []
  globalThis.IntersectionObserver = class { constructor(callback) { this.callback = callback; observers.push(this) } observe() {} disconnect() {} }
  const media = { thumbnail: '/media/NGC6269-survey.jpg', mediaKind: 'survey', mediaProvider: 'NASA SkyView / DSS2', sourceUrl: 'https://skyview.gsfc.nasa.gov/', imageCredit: 'NASA SkyView / DSS2', note: '按天体坐标获取的真实巡天图像。' }
  let calls = 0
  globalThis.fetch = async (url) => {
    assert.equal(url, '/api/objects/NGC6269/media')
    calls++
    return new Response(JSON.stringify(calls === 1 ? { error: 'NASA 配图暂不可用' } : media), { status: calls === 1 ? 503 : 200, headers: { 'Content-Type': 'application/json' } })
  }
  const root = createRoot(document.querySelector('#root'))
  const unknown = { id: 'NGC6269', name: 'NGC6269', label: 'NGC6269', category: 'deepSky', type: '星系', magnitude: 12.6 }
  const props = { result: { metadata: { filename: 'sky.jpg' }, wcs: {}, objects: [unknown], raw: {} }, settings: DEFAULT_SETTINGS, onSettingsChange() {}, onApplySettings() {}, onSelect(object) { props.selectedId = object.id; root.render(createElement(ResultSidebar, props)) }, onOpenSkyMap() {} }
  try {
    await act(async () => root.render(createElement(ResultSidebar, props)))
    await act(async () => document.querySelector('#inspector-tab-catalog').click())
    assert.equal(calls, 0)
    await act(async () => observers[0].callback([{ isIntersecting: true }]))
    assert.equal(calls, 1)
    assert.match(document.querySelector('.catalog-image-placeholder').textContent, /重试/)
    await act(async () => document.querySelector('.catalog-image-cell button').click())
    assert.equal(calls, 2, 'table retry and selected detail must reuse one pending request')
    assert.equal(document.querySelector('.catalog-detail img').getAttribute('src'), media.thumbnail)
    assert.equal(document.querySelector('.catalog-image-cell img').getAttribute('src'), media.thumbnail)
    assert.match(document.querySelector('.catalog-detail figcaption').textContent, /NASA 巡天档案/)
    assert.doesNotMatch(document.querySelector('.catalog-detail figcaption').textContent, /官方照片/)
    assert.match(document.querySelector('.catalog-detail').textContent, /真实巡天图像/)
  } finally {
    await act(async () => root.unmount())
    dom.window.close()
    if (prior.window === undefined) delete globalThis.window; else globalThis.window = prior.window
    if (prior.document === undefined) delete globalThis.document; else globalThis.document = prior.document
    if (prior.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT; else globalThis.IS_REACT_ACT_ENVIRONMENT = prior.act
    if (prior.observer === undefined) delete globalThis.IntersectionObserver; else globalThis.IntersectionObserver = prior.observer
    globalThis.fetch = prior.fetch
  }
})

test('selected DSO details start compact and disappear when browsing the stellar catalogue', async () => {
  const dom = new JSDOM('<div id="root"></div>', { pretendToBeVisual: true, url: 'http://localhost' })
  const prior = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT }
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const root = createRoot(document.querySelector('#root'))
  const nebula = { id: 'M42', name: 'M42', label: 'M42 猎户座大星云', category: 'deepSky', thumbnail: '/media/m42.jpg', mediaKind: 'official', description: '详细的天体介绍。'.repeat(80), imageCredit: 'NASA / ESA', sourceUrl: 'https://science.nasa.gov/' }
  const star = { id: 'HIP26727', name: '参宿一', label: '参宿一', category: 'brightStars', magnitude: 1.74 }
  const props = { result: { metadata: { filename: 'orion.jpg' }, wcs: {}, objects: [nebula, star], raw: {} }, selectedId: nebula.id, settings: DEFAULT_SETTINGS, onSettingsChange() {}, onApplySettings() {}, onSelect() {}, onOpenSkyMap() {} }
  try {
    await act(async () => root.render(createElement(ResultSidebar, props)))
    const detail = document.querySelector('.catalog-detail')
    const disclosure = detail.querySelector('details')
    assert.equal(disclosure.open, false, 'long descriptions and coordinates must not push the table out of view')
    assert.match(disclosure.querySelector('summary').textContent, /天体资料与坐标/)
    assert.ok(disclosure.querySelector('.image-info-list'))
    assert.equal(detail.querySelector('figure').closest('details'), null, 'the reference image stays visible')
    assert.equal(detail.querySelector('.catalog-detail-heading a').closest('details'), null, 'source attribution remains reachable without expansion')
    assert.match(detail.querySelector('figcaption').textContent, /NASA 官方照片/)
    const inspector = document.querySelector('.inspector-content')
    inspector.scrollTop = 400
    const stellarCategory = [...document.querySelectorAll('.catalog-categories button')].find(button => button.textContent.startsWith('恒星'))
    await act(async () => stellarCategory.click())
    assert.equal(document.querySelector('.catalog-detail'), null, 'an unrelated nebula detail must not stay over the stellar list')
    assert.equal(inspector.scrollTop, 0)
    assert.match(document.querySelector('.catalog-table tbody').textContent, /参宿一/)
  } finally {
    await act(async () => root.unmount())
    dom.window.close()
    if (prior.window === undefined) delete globalThis.window; else globalThis.window = prior.window
    if (prior.document === undefined) delete globalThis.document; else globalThis.document = prior.document
    if (prior.act === undefined) delete globalThis.IS_REACT_ACT_ENVIRONMENT; else globalThis.IS_REACT_ACT_ENVIRONMENT = prior.act
  }
})
