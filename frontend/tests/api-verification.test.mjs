import assert from 'node:assert/strict'
import { test } from 'node:test'
import { loadSource } from './load-source.mjs'

const { normalizeAnalysisResult } = await loadSource('api.ts')

test('wide-field verification keeps backend evidence and original dimensions without inventing EXIF', () => {
  const verification = { mode: 'wide-field', matchedStars: 82, heldOutStars: 27, heldOutOutsideCrop: 19, rmsePixels: 1.27, heldOutRmsePixels: 1.83, heldOutRmseArcsec: 97.2, spanFractionX: .78, spanFractionY: .84, patternStars: 12, patternProbability: .000001 }
  const result = normalizeAnalysisResult({ metadata: { width: 4032, height: 3024 }, wcs: { matchedStars: 12, verification } }, { name: 'phone-original.jpg' })
  assert.deepEqual(result.wcs.verification, verification)
  assert.equal(result.metadata.width, 4032)
  assert.equal(result.metadata.height, 3024)
  assert.equal(result.metadata.camera, undefined)
  assert.equal(result.metadata.focalLength, undefined)
  assert.equal(result.metadata.exposure, undefined)
  assert.equal(result.metadata.capturedAt, undefined)
  const ordinary = normalizeAnalysisResult({ wcs: { matchedStars: 82 } }, { name: 'ordinary.jpg' })
  assert.equal(ordinary.wcs.verification, undefined, 'ordinary solver counts cannot manufacture independent validation evidence')
})
