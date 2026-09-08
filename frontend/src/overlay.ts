import type { AnalysisSettings, DetectedObject } from './types'

export const annotationCoordinate = (value: number | undefined, extent: number): number | undefined =>
  value === undefined ? undefined : Math.abs(value) <= 1 ? value * extent : value

export function markerGeometry(object: DetectedObject, width: number, height: number, settings: AnalysisSettings) {
  const unit = width / 1920
  const lineWidth = Math.max(1, settings.annotationLineWidth * unit)
  const sourceRadius = object.radius && object.radius <= 1 ? object.radius * Math.min(width, height) : object.radius ?? 0
  const radius = object.category === 'deepSky'
    ? Math.max(8 * unit, sourceRadius + 5 * unit, lineWidth * 3 + 2)
    : Math.max((7 + Math.max(0, 4 - (object.magnitude ?? 6)) * 1.2) * unit, lineWidth * 3 + 3)
  const coreRadius = object.category === 'deepSky'
    ? Math.min(radius * .65, Math.max(3, 10 * unit))
    : Math.max(2, radius - lineWidth * 2 - Math.max(1, 2 * unit))
  return { x: annotationCoordinate(object.x, width), y: annotationCoordinate(object.y, height), radius, coreRadius, lineWidth, fontSize: Math.max(8, settings.annotationFontSize * unit) }
}

/** Select drawing density independently from complete catalogue inventory. */
export function selectOverlayObjects(
  objects: DetectedObject[],
  settings: AnalysisSettings,
  maxLabels?: number,
): DetectedObject[] {
  const enabled = objects.filter((object) => settings[object.category].enabled)
  const lines = enabled.filter((object) => object.category === 'constellations' && object.lines?.length)
  const cap = maxLabels ?? ({ sparse: 35, balanced: 90, dense: 180 }[settings.labelDensity])
  const eligible = enabled.filter(object => object.category !== 'constellations')
    .filter(object => settings.includeCatalogOnly || object.detected !== false)
  const deep = eligible.filter(object => object.category === 'deepSky')
    .sort((a, b) => Number((b.raw as Record<string, unknown>)?.priority ?? 0) - Number((a.raw as Record<string, unknown>)?.priority ?? 0))
  const stars = eligible.filter(object => object.category === 'brightStars')
    .sort((a, b) => (a.magnitude ?? 99) - (b.magnitude ?? 99))
  const labels = [...deep, ...stars].slice(0, cap)
  return [...lines, ...labels]
}

type Box = [number, number, number, number]
const overlaps = (a: Box, b: Box) => !(a[2] + 3 < b[0] || b[2] + 3 < a[0] || a[3] + 3 < b[1] || b[3] + 3 < a[1])

/** Place small labels outside rings and neighbouring target cores. */
export function layoutOverlayObjects(objects: DetectedObject[], width: number, height: number, settings: AnalysisSettings): DetectedObject[] {
  const occupied: Box[] = objects.filter(o => o.category !== 'constellations').flatMap(object => {
    const { x, y, coreRadius } = markerGeometry(object, width, height, settings)
    return x === undefined || y === undefined ? [] : [[x - coreRadius - 2, y - coreRadius - 2, x + coreRadius + 2, y + coreRadius + 2] as Box]
  })
  const context = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d')
  return objects.map(object => {
    if (object.category === 'constellations') return object
    const { x, y, radius, fontSize } = markerGeometry(object, width, height, settings)
    if (x === undefined || y === undefined) return object
    if (context) context.font = `${settings.fontWeight} ${fontSize}px "Microsoft YaHei", sans-serif`
    const tw = context?.measureText(object.label).width ?? [...object.label].length * fontSize * .7
    const th = fontSize * 1.15
    const gap = Math.max(3, fontSize * .35)
    const candidates = [[x + radius + gap, y], [x - radius - gap - tw, y], [x - tw / 2, y + radius + gap + th / 2], [x - tw / 2, y - radius - gap - th / 2]]
    const choice = candidates.find(([left, middle]) => {
      const box: Box = [left, middle - th / 2, left + tw, middle + th / 2]
      if (box[0] < 2 || box[1] < 2 || box[2] > width - 2 || box[3] > height - 2 || occupied.some(previous => overlaps(box, previous))) return false
      occupied.push(box)
      return true
    })
    return choice ? { ...object, labelX: choice[0], labelY: choice[1] } : { ...object, label: '' }
  })
}
