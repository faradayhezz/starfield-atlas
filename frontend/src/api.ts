import type {
  AnalysisResult,
  AnalysisSettings,
  DetectedObject,
  ImageMetadata,
  NativeExportMetadata,
  LayerKey,
  Point,
  SkyCoordinate,
  SkyCatalog,
  SkyMapManifest,
  WcsSummary,
} from './types'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const valueAt = (record: Record<string, unknown>, keys: string[]): unknown => {
  for (const key of keys) {
    if (record[key] !== undefined && record[key] !== null) return record[key]
  }
  return undefined
}

const stringAt = (record: Record<string, unknown>, keys: string[]): string | undefined => {
  const value = valueAt(record, keys)
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (typeof value === 'number') return String(value)
  return undefined
}

const numberAt = (record: Record<string, unknown>, keys: string[]): number | undefined => {
  const value = valueAt(record, keys)
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return undefined
}

const booleanAt = (record: Record<string, unknown>, keys: string[]): boolean | undefined => {
  const value = valueAt(record, keys)
  if (typeof value === 'boolean') return value
  if (value === 'true' || value === 1) return true
  if (value === 'false' || value === 0) return false
  return undefined
}

const normalizeCategory = (value: unknown, fallback: LayerKey = 'deepSky'): LayerKey => {
  const category = typeof value === 'string' ? value.toLowerCase().replace(/[\s_-]/g, '') : ''
  if (['star', 'stars', 'brightstar', 'brightstars'].includes(category)) return 'brightStars'
  if (['constellation', 'constellations', 'asterism', 'line'].includes(category)) return 'constellations'
  if (['dso', 'deepsky', 'deepskyobject', 'galaxy', 'nebula', 'cluster'].includes(category)) return 'deepSky'
  return fallback
}

const normalizePoint = (value: unknown): Point | undefined => {
  if (Array.isArray(value) && value.length >= 2) {
    const x = Number(value[0])
    const y = Number(value[1])
    return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : undefined
  }
  if (isRecord(value)) {
    const x = numberAt(value, ['x', 'pixel_x', 'px'])
    const y = numberAt(value, ['y', 'pixel_y', 'py'])
    return x !== undefined && y !== undefined ? { x, y } : undefined
  }
  return undefined
}

const normalizeLines = (value: unknown): Point[][] | undefined => {
  if (!Array.isArray(value)) return undefined
  const lines = value
    .map((line) => {
      if (!Array.isArray(line)) return []
      return line.map(normalizePoint).filter((point): point is Point => point !== undefined)
    })
    .filter((line) => line.length >= 2)
  return lines.length ? lines : undefined
}

const normalizeSkyCoordinates = (value: unknown): SkyCoordinate[] | undefined => {
  if (!Array.isArray(value)) return undefined
  const coordinates = value.map((item) => {
    if (Array.isArray(item) && item.length >= 2) {
      const raDeg = Number(item[0])
      const decDeg = Number(item[1])
      return Number.isFinite(raDeg) && Number.isFinite(decDeg) ? { raDeg, decDeg } : undefined
    }
    if (!isRecord(item)) return undefined
    const raDeg = numberAt(item, ['raDeg', 'ra_deg', 'ra'])
    const decDeg = numberAt(item, ['decDeg', 'dec_deg', 'dec'])
    return raDeg !== undefined && decDeg !== undefined ? { raDeg, decDeg } : undefined
  }).filter((item): item is SkyCoordinate => item !== undefined)
  return coordinates.length ? coordinates : undefined
}

const normalizeObject = (value: unknown, index: number, fallback: LayerKey): DetectedObject | undefined => {
  if (!isRecord(value)) return undefined
  const position = normalizePoint(valueAt(value, ['position', 'pixel', 'centroid']))
  const label = stringAt(value, [
    'display_name',
    'label',
    'constellationNameZh',
    'constellationName',
    'commonNameZh',
    'constellation',
    'name',
    'catalog_name',
    'id',
  ]) ?? `未命名天体 ${index + 1}`
  const name = stringAt(value, ['name', 'catalog_name', 'id']) ?? label
  const id = stringAt(value, ['id', 'catalog_id', 'uid']) ?? `${fallback}-${index}-${name}`
  const category = normalizeCategory(valueAt(value, ['category', 'layer', 'kind', 'object_class']), fallback)
  const magnitude = numberAt(value, ['magnitude', 'mag', 'visual_magnitude', 'vmag'])
  const confidence = numberAt(value, ['confidence', 'score', 'detection_confidence'])
  const width = numberAt(value, ['radiusPx', 'radius', 'marker_radius', 'size_px', 'pixel_radius'])
  const segmentStart = normalizePoint(valueAt(value, ['from', 'start', 'p1']))
  const segmentEnd = normalizePoint(valueAt(value, ['to', 'end', 'p2']))
  const x1 = numberAt(value, ['x1'])
  const y1 = numberAt(value, ['y1'])
  const x2 = numberAt(value, ['x2'])
  const y2 = numberAt(value, ['y2'])
  const directSegment = x1 !== undefined && y1 !== undefined && x2 !== undefined && y2 !== undefined
    ? [[{ x: x1, y: y1 }, { x: x2, y: y2 }]]
    : undefined
  const majorArcmin = numberAt(value, ['majorArcmin', 'major_arcmin'])
  const minorArcmin = numberAt(value, ['minorArcmin', 'minor_arcmin'])
  const angularSize = stringAt(value, ['angular_size', 'size', 'apparent_size']) ??
    (majorArcmin !== undefined ? `${majorArcmin.toFixed(majorArcmin < 10 ? 1 : 0)}′${minorArcmin !== undefined ? ` × ${minorArcmin.toFixed(minorArcmin < 10 ? 1 : 0)}′` : ''}` : undefined)

  return {
    id,
    name,
    label,
    category,
    constellation: stringAt(value, ['constellation', 'constellationId', 'constellation_id']),
    type: stringAt(value, ['objectTypeZh', 'type_name', 'type', 'objectType', 'object_type', 'subtype', 'classification']),
    objectClassDetail: stringAt(value, ['objectClassDetail', 'object_class_detail']),
    description: stringAt(value, ['description', 'summary', 'details']),
    titleEn: stringAt(value, ['titleEn', 'title_en', 'english_name']),
    distance: stringAt(value, ['distance', 'distance_text']),
    magnitude,
    angularSize,
    ra: stringAt(value, ['ra_text', 'ra', 'raDeg', 'ra_deg', 'right_ascension']),
    dec: stringAt(value, ['dec_text', 'dec', 'decDeg', 'dec_deg', 'declination']),
    raDeg: numberAt(value, ['raDeg', 'ra_deg', 'right_ascension_deg']),
    decDeg: numberAt(value, ['decDeg', 'dec_deg', 'declination_deg']),
    confidence,
    detected: booleanAt(value, ['defaultVisible', 'detected', 'image_detected', 'expectedVisible', 'expected_visible', 'visible']),
    defaultVisible: booleanAt(value, ['defaultVisible']),
    recommendedLabel: booleanAt(value, ['recommendedLabel']),
    evidence: stringAt(value, ['evidence']),
    pixelDetected: booleanAt(value, ['pixelDetected']),
    x: numberAt(value, ['x', 'pixel_x', 'cx']) ?? position?.x,
    y: numberAt(value, ['y', 'pixel_y', 'cy']) ?? position?.y,
    radius: width,
    labelX: numberAt(value, ['label_x', 'text_x']),
    labelY: numberAt(value, ['label_y', 'text_y']),
    lines: normalizeLines(valueAt(value, ['lines', 'segments', 'polyline'])) ?? directSegment ?? (segmentStart && segmentEnd ? [[segmentStart, segmentEnd]] : undefined),
    thumbnail: stringAt(value, ['thumbnail', 'thumbnail_url', 'preview']),
    thumbnailWidth: numberAt(value, ['thumbnailWidth', 'thumbnail_width']),
    thumbnailHeight: numberAt(value, ['thumbnailHeight', 'thumbnail_height']),
    sourceUrl: stringAt(value, ['sourceUrl', 'source_url']),
    imageCredit: stringAt(value, ['imageCredit', 'image_credit', 'credit']),
    nasaId: stringAt(value, ['nasaId', 'nasa_id']),
    mediaProvider: stringAt(value, ['mediaProvider', 'media_provider']),
    mediaUsageUrl: stringAt(value, ['mediaUsageUrl', 'media_usage_url']),
    raw: value,
  }
}

const arraysFrom = (root: Record<string, unknown>): Array<{ values: unknown[]; fallback: LayerKey }> => {
  const groups: Array<{ values: unknown[]; fallback: LayerKey }> = []
  const add = (value: unknown, fallback: LayerKey) => {
    if (Array.isArray(value)) groups.push({ values: value, fallback })
  }

  add(valueAt(root, ['objects', 'detections', 'annotations', 'catalog_objects']), 'deepSky')
  add(valueAt(root, ['deep_sky_objects', 'deepSkyObjects', 'dso']), 'deepSky')
  add(valueAt(root, ['bright_stars', 'brightStars', 'stars']), 'brightStars')
  add(valueAt(root, ['constellations', 'constellation_lines', 'constellationSegments']), 'constellations')

  const resultNode = valueAt(root, ['result', 'results', 'data'])
  if (Array.isArray(resultNode)) add(resultNode, 'deepSky')
  if (isRecord(resultNode)) {
    add(valueAt(resultNode, ['objects', 'detections', 'annotations']), 'deepSky')
    add(valueAt(resultNode, ['deep_sky_objects', 'deepSkyObjects', 'dso']), 'deepSky')
    add(valueAt(resultNode, ['bright_stars', 'brightStars', 'stars']), 'brightStars')
    add(valueAt(resultNode, ['constellations', 'constellation_lines', 'constellationSegments']), 'constellations')
  }
  return groups
}

const imageSource = (value: unknown): string | undefined => {
  if (typeof value !== 'string' || !value) return undefined
  if (/^(data:|blob:|https?:|\/)/.test(value)) return value
  const compact = value.replace(/\s/g, '')
  if (/^[A-Za-z0-9+/]+=*$/.test(compact) && compact.length > 64) return `data:image/png;base64,${compact}`
  return value
}

const normalizeMetadata = (root: Record<string, unknown>, file: File): ImageMetadata => {
  const metadataNode = valueAt(root, ['metadata', 'image_info', 'imageInfo', 'exif'])
  const metadata = isRecord(metadataNode) ? metadataNode : {}
  const imageNode = valueAt(root, ['image', 'dimensions'])
  const image = isRecord(imageNode) ? imageNode : {}
  const width = numberAt(metadata, ['width', 'image_width']) ?? numberAt(image, ['width', 'image_width']) ?? numberAt(root, ['width', 'image_width'])
  const height = numberAt(metadata, ['height', 'image_height']) ?? numberAt(image, ['height', 'image_height']) ?? numberAt(root, ['height', 'image_height'])
  const focalLength = stringAt(metadata, ['focal_length', 'focalLength', 'focal_length_mm'])
  const exposure = stringAt(metadata, ['exposure', 'exposure_time', 'exposure_seconds', 'shutter_speed'])
  const aperture = stringAt(metadata, ['aperture', 'f_number', 'fNumber'])
  const iso = stringAt(metadata, ['iso', 'iso_speed'])
  const shootingParams = stringAt(metadata, ['exposureLabel', 'exposure_label', 'shooting_params', 'shootingParams']) ??
    [focalLength, exposure, aperture, iso && `ISO ${iso.replace(/^ISO\s*/i, '')}`].filter(Boolean).join(' · ')

  return {
    filename: stringAt(metadata, ['filename', 'file_name', 'name']) ?? stringAt(root, ['filename', 'file_name']) ?? file.name,
    width,
    height,
    shootingParams: shootingParams || undefined,
    camera: [stringAt(metadata, ['camera_make', 'make']), stringAt(metadata, ['camera', 'camera_model', 'model'])].filter(Boolean).join(' ') || undefined,
    lens: stringAt(metadata, ['lens', 'lens_model']),
    focalLength,
    exposure,
    aperture,
    iso,
    capturedAt: stringAt(metadata, ['captured_at', 'capture_time', 'datetime_original', 'date_time_original', 'taken_at']),
    latitude: numberAt(metadata, ['latitude', 'gps_latitude', 'lat']),
    longitude: numberAt(metadata, ['longitude', 'gps_longitude', 'lon', 'lng']),
    analyzedAt: stringAt(metadata, ['analyzed_at', 'analysis_time', 'recognized_at']) ?? new Date().toISOString(),
  }
}

const normalizeWcs = (root: Record<string, unknown>): WcsSummary => {
  const node = valueAt(root, ['wcs', 'solution', 'plate_solution', 'astrometry'])
  const wcs = isRecord(node) ? node : {}
  const matchedStars = numberAt(wcs, ['matched_stars', 'matchedStars', 'matched_sources', 'matches'])
  const catalogStars = numberAt(wcs, ['catalog_stars', 'catalogStars', 'total_stars'])
  const matchRate = numberAt(wcs, ['match_rate', 'matchRate', 'confidence'])
  const fieldWidth = numberAt(wcs, ['horizontal_fov_deg', 'field_width_deg', 'fieldWidthDeg', 'width_deg'])
  const fieldHeight = numberAt(wcs, ['vertical_fov_deg', 'field_height_deg', 'fieldHeightDeg', 'height_deg'])
  const fov = stringAt(wcs, ['field_of_view', 'fieldOfView', 'fov']) ??
    (fieldWidth !== undefined && fieldHeight !== undefined ? `${fieldWidth.toFixed(2)}° × ${fieldHeight.toFixed(2)}°` : undefined)
  const center = stringAt(wcs, ['center_coordinates', 'centerCoordinates', 'center'])
  const ra = stringAt(wcs, ['ra', 'center_ra', 'center_ra_deg'])
  const dec = stringAt(wcs, ['dec', 'center_dec', 'center_dec_deg'])
  const pixelScale = numberAt(wcs, ['pixel_scale_arcsec'])
  const rotation = numberAt(wcs, ['roll_deg', 'rotation', 'orientation'])
  const rmsError = numberAt(wcs, ['rmse_arcsec', 'rms_error', 'rmsError', 'residual'])
  const centerRaDeg = numberAt(wcs, ['center_ra_deg', 'centerRaDeg'])
  const centerDecDeg = numberAt(wcs, ['center_dec_deg', 'centerDecDeg'])
  return {
    matchedStars,
    catalogStars,
    matchRate,
    fieldOfView: fov,
    centerCoordinates: center ?? (ra && dec ? `RA ${ra} · Dec ${dec}` : undefined),
    pixelScale: stringAt(wcs, ['pixel_scale', 'pixelScale']) ?? (pixelScale !== undefined ? `${pixelScale.toFixed(2)}″/px` : undefined),
    rotation: rotation !== undefined ? `${rotation.toFixed(2)}°` : stringAt(wcs, ['roll_deg', 'rotation', 'orientation']),
    rmsError: rmsError !== undefined ? `${rmsError.toFixed(1)}″` : stringAt(wcs, ['rmse_arcsec', 'rms_error', 'rmsError', 'residual']),
    centerRaDeg,
    centerDecDeg,
    horizontalFovDeg: fieldWidth,
    verticalFovDeg: fieldHeight,
    rollDeg: rotation,
    frameCorners: normalizeSkyCoordinates(valueAt(wcs, ['frame_corners_radec', 'frameCorners', 'corners'])),
    frameBoundary: normalizeSkyCoordinates(valueAt(wcs, ['frame_boundary_radec', 'frameBoundary', 'footprint'])),
  }
}

export const normalizeAnalysisResult = (payload: unknown, file: File): AnalysisResult => {
  const root = isRecord(payload) ? payload : {}
  const objects = arraysFrom(root).flatMap(({ values, fallback }) =>
    values.map((value, index) => normalizeObject(value, index, fallback)).filter((item): item is DetectedObject => item !== undefined),
  )
  const uniqueObjects = [...new Map(objects.map((object) => [object.id, object])).values()]
  const consolidatedObjects: DetectedObject[] = []
  const constellationGroups = new Map<string, DetectedObject>()
  const constellationEndpoints = new Map<string, { groupKey: string; point: Point; count: number }>()
  uniqueObjects.forEach((object) => {
    if (object.category !== 'constellations') {
      consolidatedObjects.push(object)
      return
    }
    const groupKey = object.constellation || object.label || '星座连线'
    const raw = isRecord(object.raw) ? object.raw : {}
    const sourceSegment = raw.sourceSegment ?? object.id
    for (const line of object.lines ?? []) {
      for (const point of [line[0], line[line.length - 1]]) {
        const key = `${sourceSegment}:${point.x.toFixed(2)}:${point.y.toFixed(2)}`
        const endpoint = constellationEndpoints.get(key)
        if (endpoint) endpoint.count += 1
        else constellationEndpoints.set(key, { groupKey, point, count: 1 })
      }
    }
    const existing = constellationGroups.get(groupKey)
    if (existing) existing.lines = [...(existing.lines ?? []), ...(object.lines ?? [])]
    else constellationGroups.set(groupKey, { ...object, id: `constellation-${groupKey}` })
  })
  for (const endpoint of constellationEndpoints.values()) {
    if (endpoint.count !== 1) continue
    const group = constellationGroups.get(endpoint.groupKey)
    if (group) (group.protectedPoints ??= []).push(endpoint.point)
  }
  consolidatedObjects.push(...constellationGroups.values())
  const nested = valueAt(root, ['result', 'data'])
  const nestedRecord = isRecord(nested) ? nested : {}
  const annotated = valueAt(root, ['annotatedImageUrl', 'annotatedImage', 'annotated_image', 'annotated_image_url', 'image_url', 'preview_url']) ??
    valueAt(nestedRecord, ['annotatedImageUrl', 'annotatedImage', 'annotated_image', 'annotated_image_url', 'image_url', 'preview_url'])
  const countsNode = valueAt(root, ['counts', 'summary'])
  const countsRecord = isRecord(countsNode) ? countsNode : {}
  const warningsNode = valueAt(root, ['warnings', 'warning'])

  return {
    jobId: stringAt(root, ['jobId', 'job_id']),
    status: stringAt(root, ['status']),
    metadata: normalizeMetadata(root, file),
    wcs: normalizeWcs(root),
    objects: consolidatedObjects,
    annotatedImage: imageSource(annotated),
    originalImage: imageSource(valueAt(root, ['originalImageUrl', 'original_image_url', 'originalImage', 'original_image'])),
    downloadUrl: imageSource(valueAt(root, ['downloadUrl', 'download_url'])),
    resultsUrl: imageSource(valueAt(root, ['resultsUrl', 'results_url'])),
    originalDownloadUrl: imageSource(valueAt(root, ['originalDownloadUrl', 'original_download_url'])),
    export: isRecord(root.export) ? root.export as unknown as NativeExportMetadata : undefined,
    counts: {
      deepSky: numberAt(countsRecord, ['deepSky', 'deep_sky', 'dso']),
      expectedVisible: numberAt(countsRecord, ['expectedVisible', 'expected_visible']),
      brightStars: numberAt(countsRecord, ['brightStars', 'bright_stars', 'stars']),
      constellations: numberAt(countsRecord, ['constellations', 'constellationSegments', 'constellation_segments']),
    },
    warnings: Array.isArray(warningsNode) ? warningsNode.filter((warning): warning is string => typeof warning === 'string') : typeof warningsNode === 'string' ? [warningsNode] : [],
    raw: payload,
  }
}

const parseError = async (response: Response): Promise<string> => {
  try {
    const payload: unknown = await response.json()
    if (isRecord(payload)) return stringAt(payload, ['message', 'detail', 'error']) ?? `请求失败（${response.status}）`
  } catch {
    const message = await response.text().catch(() => '')
    if (message.trim()) return message.trim()
  }
  return `请求失败（${response.status} ${response.statusText}）`
}

export interface AnalysisTaskProgressResponse {
  status: string
  stage: string
  percent: number
  message: string
  receivedBytes?: number
  totalBytes?: number
  updatedAt?: string
}

const normalizeTaskProgress = (payload: unknown): AnalysisTaskProgressResponse | undefined => {
  if (!isRecord(payload)) return undefined
  return {
    status: stringAt(payload, ['status']) ?? 'running',
    stage: stringAt(payload, ['stage']) ?? 'preparing',
    percent: Math.max(0, Math.min(100, numberAt(payload, ['percent']) ?? 0)),
    message: stringAt(payload, ['message', 'detail']) ?? '正在准备识别',
    receivedBytes: numberAt(payload, ['receivedBytes', 'received_bytes']),
    totalBytes: numberAt(payload, ['totalBytes', 'total_bytes']),
    updatedAt: stringAt(payload, ['updatedAt', 'updated_at']),
  }
}

export async function getAnalysisProgress(requestId: string, signal?: AbortSignal): Promise<AnalysisTaskProgressResponse | undefined> {
  const response = await fetch(`/api/progress/${encodeURIComponent(requestId)}`, {
    signal,
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  if (response.status === 404) return undefined
  if (!response.ok) throw new Error(await parseError(response))
  return normalizeTaskProgress(await response.json())
}

export async function cancelAnalysis(requestId: string): Promise<void> {
  const response = await fetch(`/api/progress/${encodeURIComponent(requestId)}`, {
    method: 'DELETE',
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  if (response.status === 404 || response.status === 409) return
  if (!response.ok) throw new Error(await parseError(response))
}

export async function analyzePhoto(file: File, settings: AnalysisSettings, requestId: string, signal?: AbortSignal): Promise<AnalysisResult> {
  const params = new URLSearchParams({
    deepSky: String(settings.deepSky.enabled),
    brightStars: String(settings.brightStars.enabled),
    constellations: String(settings.constellations.enabled),
    dsoThreshold: String(settings.deepSky.value),
    starThreshold: String(settings.brightStars.value),
    constellationStrength: String(settings.constellations.value),
    catalogDepth: settings.catalogDepth,
    labelDensity: settings.labelDensity,
    deepSkyColor: settings.deepSkyColor,
    brightStarColor: settings.brightStarColor,
    constellationColor: settings.constellationColor,
    fontWeight: String(settings.fontWeight),
    highContrast: String(settings.highContrast),
    annotationOpacity: String(settings.annotationOpacity),
    annotationLineWidth: String(settings.annotationLineWidth),
    annotationFontSize: String(settings.annotationFontSize),
    markerStyle: settings.markerStyle,
    starMagnitudeLimit: String(settings.starMagnitudeLimit),
    includeCatalogOnly: String(settings.includeCatalogOnly),
    deep_sky: String(settings.deepSky.enabled),
    bright_stars: String(settings.brightStars.enabled),
    dso_threshold: String(settings.deepSky.value),
    star_threshold: String(settings.brightStars.value),
    constellation_strength: String(settings.constellations.value),
  })

  const response = await fetch(`/api/analyze?${params.toString()}`, {
    method: 'POST',
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
      'X-Filename': encodeURIComponent(file.name),
      'X-Filename-Encoding': 'percent',
      'X-Request-Id': requestId,
      Accept: 'application/json, image/png',
    },
    body: file,
    signal,
  })

  if (!response.ok) throw new Error(await parseError(response))
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
  if (contentType.startsWith('image/')) {
    const blob = await response.blob()
    return {
      metadata: { filename: file.name, analyzedAt: new Date().toISOString() },
      wcs: {},
      objects: [],
      annotatedImage: URL.createObjectURL(blob),
      downloadUrl: undefined,
      resultsUrl: undefined,
      raw: { responseType: contentType },
    }
  }
  const payload: unknown = await response.json()
  if (isRecord(payload) && String(payload.status ?? '').toLowerCase() === 'error') {
    throw new Error(stringAt(payload, ['error', 'message', 'detail']) ?? '识别失败')
  }
  return normalizeAnalysisResult(payload, file)
}

export async function exportAnnotatedPhoto(jobId: string, settings: AnalysisSettings, signal?: AbortSignal): Promise<{ downloadUrl: string; export: NativeExportMetadata }> {
  const response = await fetch(`/api/export/${encodeURIComponent(jobId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ settings: {
      ...settings,
      deepSky: settings.deepSky.enabled,
      brightStars: settings.brightStars.enabled,
      constellations: settings.constellations.enabled,
      dsoThreshold: settings.deepSky.value,
      starThreshold: settings.brightStars.value,
      constellationStrength: settings.constellations.value,
    } }),
    signal,
  })
  if (!response.ok) throw new Error(await parseError(response))
  return response.json() as Promise<{ downloadUrl: string; export: NativeExportMetadata }>
}

export async function getSkyMapManifest(signal?: AbortSignal): Promise<SkyMapManifest> {
  const response = await fetch('/api/sky-map/manifest', {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(await parseError(response))
  return response.json() as Promise<SkyMapManifest>
}

export async function getSkyCatalog(signal?: AbortSignal): Promise<SkyCatalog> {
  const response = await fetch('/api/sky-map/catalog', {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(await parseError(response))
  return response.json() as Promise<SkyCatalog>
}
