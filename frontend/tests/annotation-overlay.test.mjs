import assert from 'node:assert/strict'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { loadSource } from './load-source.mjs'

const { markerGeometry, selectOverlayObjects, layoutOverlayObjects } = await loadSource('overlay.ts')
const { DEFAULT_SETTINGS } = await loadSource('types.ts')
const { StarCanvas } = await loadSource('components/StarCanvas.tsx')
const object = (id, category = 'deepSky', overrides = {}) => ({ id, name: id, label: id, category, x: 960, y: 640, detected: true, ...overrides })

test('overlapping hollow markers remain complete even with text contrast enabled', () => {
  const objects = [object('NGC6261', 'deepSky', { x: 950, radius: 14, magnitude: 12 }), object('NGC6263', 'deepSky', { x: 970, radius: 14, magnitude: 13 }), object('HIP01', 'brightStars', { x: 1030, magnitude: 8 }), object('line', 'constellations', { lines: [[{ x: 950, y: 640 }, { x: 1100, y: 700 }]], protectedPoints: [{ x: 950, y: 640 }, { x: 1100, y: 700 }], x: undefined, y: undefined })]
  const result = { metadata: { filename: 'cluster.jpg', width: 1920, height: 1280 }, wcs: {}, objects, raw: {} }
  const settings = { ...DEFAULT_SETTINGS, highContrast: true, constellations: { enabled: true, value: 55 } }
  const html = renderToStaticMarkup(createElement(StarCanvas, { result, settings, source: '/image.jpg', renderOverlay: true, onSelect() {}, onFile() {}, onBrowse() {} }))
  const dom = new JSDOM(html)
  try {
    const markers = dom.window.document.querySelector('.object-marker-layer')
    assert.equal(markers.querySelectorAll('circle').length, 3)
    for (const circle of markers.querySelectorAll('circle')) {
      assert.equal(circle.getAttribute('fill'), 'none')
      assert.equal(circle.getAttribute('stroke'), 'currentColor')
      assert.equal(circle.closest('[mask]'), null, 'neighbor core disks must never erase ring strokes')
    }
    assert.ok(markers.querySelector('text[stroke="#090a0b"]'), 'optional contrast belongs to text only')
    assert.equal(markers.querySelectorAll('[fill="black"], [fill="#090a0b"], path[stroke="#090a0b"]').length, 0)
    const lineLayer = dom.window.document.querySelector('.constellation-line-layer')
    assert.ok(lineLayer.hasAttribute('mask'), 'constellation endpoints still protect stellar pixels')
    assert.equal(dom.window.document.querySelectorAll('mask circle').length, 3, 'only one stellar core plus two constellation endpoints; no DSO clipping disks')
  } finally { dom.window.close() }
})

test('stellar labels have an independent budget and include non-default faint catalogue stars', () => {
  const dsos = Array.from({ length: 100 }, (_, i) => object(`NGC${i}`, 'deepSky', { x: 20 + i * 16, y: 350, raw: { priority: 100 - i } }))
  const stars = Array.from({ length: 220 }, (_, i) => object(`TYC${i}`, 'brightStars', { x: 20 + i % 30 * 60, y: 100 + Math.floor(i / 30) * 130, magnitude: 8 + i / 100, defaultVisible: false, detected: false, evidence: 'catalog_position', pixelDetected: false }))
  const selected = selectOverlayObjects([...dsos, ...stars], DEFAULT_SETTINGS)
  assert.equal(selected.filter(item => item.category === 'deepSky').length, 35)
  assert.equal(selected.filter(item => item.category === 'brightStars').length, 60)
  assert.equal(selectOverlayObjects([...dsos, ...stars], { ...DEFAULT_SETTINGS, starLabelDensity: 'dense' }).filter(item => item.category === 'brightStars').length, 180)
  assert.equal(selectOverlayObjects([...dsos, ...stars], DEFAULT_SETTINGS, 0).filter(item => item.category === 'deepSky').length, 0)
  assert.ok(selected.filter(item => item.category === 'brightStars').every(item => !item.pixelDetected && item.evidence === 'catalog_position'))
})

test('spatial selection reserves stellar slots across the photo before filling a dense bright cluster', () => {
  const cluster = Array.from({ length: 80 }, (_, i) => object(`cluster${i}`, 'brightStars', { x: 100 + i % 10, y: 100 + Math.floor(i / 10), magnitude: 5 + i / 100 }))
  const outskirts = Array.from({ length: 8 }, (_, i) => object(`outer${i}`, 'brightStars', { x: 400 + i % 4 * 360, y: 430 + Math.floor(i / 4) * 350, magnitude: 9 }))
  const settings = { ...DEFAULT_SETTINGS, starLabelDensity: 'sparse' }
  const selected = selectOverlayObjects([...cluster, ...outskirts], settings)
  assert.equal(selected.length, 20)
  assert.ok(outskirts.every(star => selected.includes(star)))
  assert.deepEqual(selectOverlayObjects([...outskirts, ...cluster].reverse(), settings).map(star => star.id), selected.map(star => star.id))
})

test('faint compact markers use fine scalable lines while large nebulae keep the base width', () => {
  assert.equal(markerGeometry(object('faint', 'deepSky', { magnitude: 13 }), 1920, 1280, DEFAULT_SETTINGS).lineWidth, .75)
  assert.equal(markerGeometry(object('unknown', 'deepSky'), 1920, 1280, DEFAULT_SETTINGS).lineWidth, .75)
  assert.equal(markerGeometry(object('star', 'brightStars', { magnitude: 8 }), 1920, 1280, DEFAULT_SETTINGS).lineWidth, .75)
  assert.equal(markerGeometry(object('bright', 'brightStars', { magnitude: 3 }), 1920, 1280, DEFAULT_SETTINGS).lineWidth, 1.25)
  assert.equal(markerGeometry(object('large', 'deepSky', { radius: 60, magnitude: 12 }), 1920, 1280, DEFAULT_SETTINGS).lineWidth, 1.25)
  assert.equal(markerGeometry(object('tiny', 'brightStars', { magnitude: 8 }), 3840, 2560, { ...DEFAULT_SETTINGS, annotationLineWidth: .5, faintMarkerScale: .3 }).lineWidth, .7)
})

test('dense field label boxes stay outside complete marker disks, not only their centers', () => {
  const settings = { ...DEFAULT_SETTINGS, highContrast: true }
  const objects = Array.from({ length: 18 }, (_, i) => object(`NGC${6200 + i}`, 'deepSky', { x: 800 + i % 6 * 32, y: 500 + Math.floor(i / 6) * 34, radius: 12, magnitude: 13 }))
  const layout = layoutOverlayObjects(objects, 1920, 1280, settings)
  const labels = layout.filter(item => item.label)
  assert.ok(labels.length >= 3)
  assert.ok(labels.some(item => item.leaderLine?.length), 'crowded labels should relocate with a leader when an unobstructed route exists')
  for (const label of labels) {
    const font = markerGeometry(label, 1920, 1280, settings).fontSize
    const halo = font * .09
    const box = [label.labelX - halo, label.labelY - font * 1.15 / 2 - halo, label.labelX + [...label.label].length * font * .7 + halo, label.labelY + font * 1.15 / 2 + halo]
    for (const target of objects) {
      const { x, y, radius, lineWidth } = markerGeometry(target, 1920, 1280, settings)
      const dx = x - Math.max(box[0], Math.min(box[2], x))
      const dy = y - Math.max(box[1], Math.min(box[3], y))
      assert.ok(Math.hypot(dx, dy) > radius + lineWidth / 2, `${label.id} label must not touch ${target.id} ring`)
    }
  }
})

test('rendered leader routes never pass through another annotation label in a crowded galaxy field', () => {
  const settings = { ...DEFAULT_SETTINGS, highContrast: true, labelDensity: 'dense', brightStars: { enabled: false, value: 60 } }
  const objects = Array.from({ length: 18 }, (_, i) => object(`NGC${6260 + i}`, 'deepSky', { x: 800 + i % 6 * 32, y: 500 + Math.floor(i / 6) * 34, radius: 12, magnitude: 13 }))
  const result = { metadata: { filename: 'crowded-galaxies.jpg', width: 1920, height: 1280 }, wcs: {}, objects, raw: {} }
  const html = renderToStaticMarkup(createElement(StarCanvas, { result, settings, source: '/image.jpg', renderOverlay: true, onSelect() {}, onFile() {}, onBrowse() {} }))
  const dom = new JSDOM(html)
  try {
    const labels = [...dom.window.document.querySelectorAll('.object-marker-layer text')]
    const leaders = [...dom.window.document.querySelectorAll('.annotation-leader')]
    assert.ok(leaders.length > 0, 'the fixture must exercise relocated labels with actual rendered leaders')
    for (const leader of leaders) {
      const points = leader.getAttribute('points').split(' ').map(point => point.split(',').map(Number))
      for (const label of labels) {
        if (label.parentNode === leader.parentNode) continue
        const x = Number(label.getAttribute('x')), y = Number(label.getAttribute('y'))
        const fontSize = Number(label.getAttribute('font-size'))
        const padding = Number(label.getAttribute('stroke-width')) / 2 + 2
        const box = [x - padding, y - fontSize * 1.15 / 2 - padding, x + [...label.textContent].length * fontSize * .7 + padding, y + fontSize * 1.15 / 2 + padding]
        for (let segment = 1; segment < points.length; segment++) {
          const start = points[segment - 1], end = points[segment]
          const steps = Math.ceil(Math.hypot(end[0] - start[0], end[1] - start[1]) * 4)
          for (let step = 0; step <= steps; step++) {
            const px = start[0] + (end[0] - start[0]) * step / steps
            const py = start[1] + (end[1] - start[1]) * step / steps
            assert.ok(px < box[0] || px > box[2] || py < box[1] || py > box[3], `${leader.parentNode.querySelector('title').textContent} leader crosses ${label.textContent}`)
          }
        }
      }
    }
  } finally { dom.window.close() }
})
