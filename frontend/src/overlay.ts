import type { AnalysisSettings, DetectedObject, Point } from './types'

export const annotationCoordinate = (value: number | undefined, extent: number): number | undefined =>
  value === undefined ? undefined : Math.abs(value) <= 1 ? value * extent : value

export function markerGeometry(object: DetectedObject, width: number, height: number, settings: AnalysisSettings) {
  const unit = width / 1920
  const baseWidth = settings.annotationLineWidth * unit
  const sourceRadius = object.radius && object.radius <= 1 ? object.radius * Math.min(width, height) : object.radius ?? 0
  const radius = object.category === 'deepSky'
    ? Math.max(2.5, 8 * unit, sourceRadius + 5 * unit, baseWidth * 3 + 2 * unit)
    : Math.max(2.5, (7 + Math.max(0, 4 - (object.magnitude ?? 6)) * 1.2) * unit, baseWidth * 3 + 3 * unit)
  const faint = object.category === 'brightStars'
    ? (object.magnitude ?? 0) >= 7
    : object.category === 'deepSky' && radius <= 24 * unit && (object.magnitude === undefined || object.magnitude >= 10 || object.detected === false)
  const lineWidth = Math.max(.35, settings.annotationLineWidth * (faint ? settings.faintMarkerScale ?? .6 : 1)) * unit
  const coreRadius = object.category === 'deepSky'
    ? Math.min(radius * .65, 10 * unit)
    : Math.max(2 * unit, radius - lineWidth * 2 - 2 * unit)
  return { x: annotationCoordinate(object.x, width), y: annotationCoordinate(object.y, height), radius, coreRadius, lineWidth, fontSize: Math.max(8 * unit, settings.annotationFontSize * unit) }
}

/** Sample the entire image before filling spare slots from the rank order. */
function spatialSample(objects: DetectedObject[], cap: number, width: number, height: number): DetectedObject[] {
  if (cap <= 0) return []
  if (objects.length <= cap) return objects
  const columns = Math.max(1, Math.ceil(Math.sqrt(cap * width / height)))
  const rows = Math.max(1, Math.ceil(cap / columns))
  const cells = new Set<string>()
  const chosen = new Set<DetectedObject>()
  for (const object of objects) {
    const x = annotationCoordinate(object.x, width)
    const y = annotationCoordinate(object.y, height)
    if (x === undefined || y === undefined) continue
    const column = Math.min(columns - 1, Math.max(0, Math.floor(x / width * columns)))
    const row = Math.min(rows - 1, Math.max(0, Math.floor(y / height * rows)))
    const cell = `${column}:${row}`
    if (cells.has(cell)) continue
    cells.add(cell)
    chosen.add(object)
    if (chosen.size >= cap) break
  }
  for (const object of objects) {
    if (chosen.size >= cap) break
    chosen.add(object)
  }
  return objects.filter(object => chosen.has(object))
}

/** The full stellar catalogue gets its own budget, independent of DSO labels. */
export function selectOverlayObjects(
  objects: DetectedObject[],
  settings: AnalysisSettings,
  maxLabels?: number,
  width = 1920,
  height = 1280,
): DetectedObject[] {
  const enabled = objects.filter((object) => settings[object.category].enabled)
  const lines = enabled.filter((object) => object.category === 'constellations' && object.lines?.length)
  const cap = maxLabels ?? ({ sparse: 35, balanced: 90, dense: 180 }[settings.labelDensity])
  const starCap = { sparse: 20, balanced: 60, dense: 180 }[settings.starLabelDensity ?? 'balanced']
  const byMagnitude = (a: DetectedObject, b: DetectedObject) => (a.magnitude ?? 99) - (b.magnitude ?? 99) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
  const deep = enabled.filter(object => object.category === 'deepSky' && (settings.includeCatalogOnly || object.detected !== false))
    .sort((a, b) => Number((b.raw as Record<string, unknown>)?.priority ?? 0) - Number((a.raw as Record<string, unknown>)?.priority ?? 0) || byMagnitude(a, b))
  const stars = enabled.filter(object => object.category === 'brightStars' && (object.magnitude === undefined || object.magnitude <= settings.starMagnitudeLimit))
    .sort(byMagnitude)
  return [...lines, ...spatialSample(deep, cap, width, height), ...spatialSample(stars, starCap, width, height)]
}

type Box = [number, number, number, number]
const overlaps = (a: Box, b: Box, gap: number) => !(a[2] + gap < b[0] || b[2] + gap < a[0] || a[3] + gap < b[1] || b[3] + gap < a[1])
const distanceToSegment = (point: Point, start: Point, end: Point): number => {
  const dx = end.x - start.x, dy = end.y - start.y
  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy || 1)))
  return Math.hypot(point.x - start.x - t * dx, point.y - start.y - t * dy)
}

const segmentIntersectsBox = (start: Point, end: Point, box: Box, padding: number): boolean => {
  let enter = 0, leave = 1
  for (const [origin, delta, low, high] of [
    [start.x, end.x - start.x, box[0] - padding, box[2] + padding],
    [start.y, end.y - start.y, box[1] - padding, box[3] + padding],
  ]) {
    if (Math.abs(delta) < 1e-9) {
      if (origin < low || origin > high) return false
      continue
    }
    const a = (low - origin) / delta, b = (high - origin) / delta
    enter = Math.max(enter, Math.min(a, b))
    leave = Math.min(leave, Math.max(a, b))
    if (enter > leave) return false
  }
  return true
}

/** Reserve complete marker disks; relocate crowded labels with thin leader lines. */
export function layoutOverlayObjects(objects: DetectedObject[], width: number, height: number, settings: AnalysisSettings): DetectedObject[] {
  const unit = width / 1920
  const markers = objects.filter(o => o.category !== 'constellations').flatMap(object => {
    const { x, y, radius, lineWidth } = markerGeometry(object, width, height, settings)
    return x === undefined || y === undefined ? [] : [{ id: object.id, x, y, radius: radius + lineWidth / 2 + 2 * unit }]
  })
  const occupied: Box[] = markers.map(({ x, y, radius }) => [x - radius, y - radius, x + radius, y + radius])
  const context = typeof document === 'undefined' ? null : document.createElement('canvas').getContext('2d')
  return objects.map(object => {
    if (object.category === 'constellations') return object
    const { x, y, radius, lineWidth, fontSize } = markerGeometry(object, width, height, settings)
    if (x === undefined || y === undefined) return object
    if (context) context.font = `${settings.fontWeight} ${fontSize}px "Microsoft YaHei", sans-serif`
    const tw = context?.measureText(object.label).width ?? [...object.label].length * fontSize * .7
    const th = fontSize * 1.15
    const halo = settings.highContrast ? fontSize * .09 : 0
    const gap = Math.max(3 * unit, fontSize * .35) + halo + lineWidth / 2
    const candidates = [0, 2, 4, 7].flatMap(offset => {
      const distance = radius + gap + offset * th
      return [
        [x + distance, y, offset], [x - distance - tw, y, offset],
        [x - tw / 2, y + distance + th / 2, offset], [x - tw / 2, y - distance - th / 2, offset],
        [x + distance, y - distance, offset], [x - distance - tw, y - distance, offset],
        [x + distance, y + distance, offset], [x - distance - tw, y + distance, offset],
      ]
    })
    for (const [left, middle, offset] of candidates) {
      const box: Box = [left - halo, middle - th / 2 - halo, left + tw + halo, middle + th / 2 + halo]
      if (box[0] < 2 * unit || box[1] < 2 * unit || box[2] > width - 2 * unit || box[3] > height - 2 * unit || occupied.some(previous => overlaps(box, previous, 2 * unit))) continue
      let leaderLine: Point[] | undefined
      if (offset > 0) {
        const end = { x: Math.max(box[0], Math.min(box[2], x)), y: Math.max(box[1], Math.min(box[3], y)) }
        const length = Math.hypot(end.x - x, end.y - y)
        const start = { x: x + (end.x - x) * (radius + 2 * unit) / length, y: y + (end.y - y) * (radius + 2 * unit) / length }
        if (markers.some(marker => marker.id !== object.id && distanceToSegment(marker, start, end) < marker.radius)) continue
        // Marker disks were checked above; the remaining reservations belong to
        // earlier text and leader routes. This label is not reserved until its
        // own route has been accepted, so its endpoint can still reach the text.
        if (occupied.slice(markers.length).some(previous => segmentIntersectsBox(start, end, previous, 2 * unit))) continue
        leaderLine = [start, end]
        occupied.push([Math.min(start.x, end.x), Math.min(start.y, end.y), Math.max(start.x, end.x), Math.max(start.y, end.y)])
      }
      occupied.push(box)
      return { ...object, labelX: left, labelY: middle, leaderLine }
    }
    return { ...object, label: '', leaderLine: undefined }
  })
}
