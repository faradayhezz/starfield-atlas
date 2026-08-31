import type { AnalysisSettings, DetectedObject } from './types'

const isPointAnnotation = (object: DetectedObject) => object.category !== 'constellations'

/**
 * Keep complete constellation geometry, but cap text-bearing markers so a
 * dense catalogue result cannot turn the photograph into a label cloud.
 * Deep-sky `detected` is normalized from the API's `expectedVisible` flag.
 */
export function selectOverlayObjects(
  objects: DetectedObject[],
  settings: AnalysisSettings,
  maxLabels = 120,
): DetectedObject[] {
  const enabled = objects.filter((object) => settings[object.category].enabled)
  const lines = enabled.filter((object) => object.category === 'constellations' && object.lines?.length)
  const labels = enabled
    .filter(isPointAnnotation)
    .filter((object) => object.detected !== false)
    .slice(0, maxLabels)

  return [...lines, ...labels]
}
