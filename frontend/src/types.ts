export type LayerKey = 'deepSky' | 'brightStars' | 'constellations'

export interface LayerSetting {
  enabled: boolean
  value: number
}

export type AnnotationFontWeight = 500 | 650 | 800

export interface AnalysisSettings {
  deepSky: LayerSetting
  brightStars: LayerSetting
  constellations: LayerSetting
  catalogDepth: 'bright' | 'balanced' | 'deep'
  labelDensity: 'sparse' | 'balanced' | 'dense'
  deepSkyColor: string
  brightStarColor: string
  constellationColor: string
  fontWeight: AnnotationFontWeight
  highContrast: boolean
  annotationOpacity: number
  annotationLineWidth: number
  annotationFontSize: number
  markerStyle: 'circle' | 'corners'
  starMagnitudeLimit: number
  includeCatalogOnly: boolean
}

export interface ImageMetadata {
  filename: string
  width?: number
  height?: number
  shootingParams?: string
  camera?: string
  lens?: string
  focalLength?: string
  exposure?: string
  aperture?: string
  iso?: string
  capturedAt?: string
  latitude?: number
  longitude?: number
  analyzedAt?: string
}

export interface WcsSummary {
  matchedStars?: number
  catalogStars?: number
  matchRate?: number
  fieldOfView?: string
  centerCoordinates?: string
  pixelScale?: string
  rotation?: string
  rmsError?: string
  centerRaDeg?: number
  centerDecDeg?: number
  horizontalFovDeg?: number
  verticalFovDeg?: number
  rollDeg?: number
  frameCorners?: SkyCoordinate[]
  frameBoundary?: SkyCoordinate[]
}

export interface SkyCoordinate {
  raDeg: number
  decDeg: number
}

export interface Point {
  x: number
  y: number
}

export interface DetectedObject {
  id: string
  name: string
  label: string
  category: LayerKey
  constellation?: string
  type?: string
  objectClassDetail?: string
  description?: string
  titleEn?: string
  distance?: string
  magnitude?: number
  angularSize?: string
  ra?: string
  dec?: string
  raDeg?: number
  decDeg?: number
  confidence?: number
  detected?: boolean
  defaultVisible?: boolean
  recommendedLabel?: boolean
  evidence?: string
  pixelDetected?: boolean
  x?: number
  y?: number
  radius?: number
  labelX?: number
  labelY?: number
  lines?: Point[][]
  protectedPoints?: Point[]
  thumbnail?: string
  thumbnailWidth?: number
  thumbnailHeight?: number
  sourceUrl?: string
  imageCredit?: string
  nasaId?: string
  mediaProvider?: string
  mediaUsageUrl?: string
  raw?: unknown
}

export interface AnalysisResult {
  jobId?: string
  status?: string
  metadata: ImageMetadata
  wcs: WcsSummary
  objects: DetectedObject[]
  annotatedImage?: string
  originalImage?: string
  downloadUrl?: string
  resultsUrl?: string
  originalDownloadUrl?: string
  export?: NativeExportMetadata
  counts?: Partial<Record<LayerKey | 'expectedVisible', number>>
  warnings?: string[]
  raw: unknown
}

export interface NativeExportMetadata {
  format: string
  extension: string
  bitDepth: number
  width: number
  height: number
  originalFormat: string
  isRaw: boolean
  note?: string
}

export interface AnalysisProgress {
  stage: number
  percent: number
  title: string
  detail: string
  stageKey?: string
  elapsedSeconds?: number
  receivedBytes?: number
  totalBytes?: number
}

export interface SkyMapAttribution {
  label: string
  /** Legacy schema used a single URL, which pointed at the license page. */
  url?: string
  sourceUrl?: string
  licenseLabel?: string
  licenseUrl?: string
}

export interface SkyMapLayerManifest {
  id: 'filled' | 'ls-dr11' | '2mass-color'
  title: string
  shortTitle: string
  description: string
  offlineMaxZoom: number
  onlineMaxZoom: number
  tileCount?: number
  totalBytes?: number
  tileVersion?: string | number
  coverageFraction?: number
  datasetCoverageFraction?: number
  renderCoverageFraction?: number
  renderDeclinationLimit?: number
  attributions?: SkyMapAttribution[]
}

export interface SkyMapManifest {
  schemaVersion?: number
  tileVersion?: string | number
  defaultLayer?: SkyMapLayerManifest['id']
  layers?: SkyMapLayerManifest[]
  offlineTotalBytes?: number
  dataset: string
  layer: string
  minZoom: number
  offlineMaxZoom: number
  onlineMaxZoom: number
  tileSize: number
  tileCount: number
  totalBytes: number
  projection?: string
  attribution: string
  license: string
  licenseUrl?: string
  officialReleaseUrl?: string
  dataReleaseUrl?: string
  viewerUrl?: string
  allSkyDataset?: string
  allSkyAttribution?: string
  allSkyLicense?: string
  allSkyLicenseUrl?: string
  allSkySourceUrl?: string
  allSkyMissionUrl?: string
  allSkyTileCount?: number
  allSkyTotalBytes?: number
  hips?: HipsManifest
}

export interface HipsSurveyManifest {
  id: 'dss2-color' | 'legacy-dr10' | '2mass-color'
  title: string
  url: string
  maxOrder: number
  tileFormat: 'jpg' | 'png'
  coverageFraction: number
  bundledOverview?: boolean
}

export interface HipsManifest {
  schemaVersion: number
  cacheMode: string
  surveys: HipsSurveyManifest[]
}

export interface SkyCatalogSource {
  id: string
  label: string
  raDeg: number
  decDeg: number
  magnitude?: number
  priority?: number
  defaultVisible?: boolean
  catalogLabel?: string
  commonNameZh?: string
  objectType?: string
  objectTypeZh?: string
  majorArcmin?: number
  minorArcmin?: number
  rank?: number
}

export interface SkyConstellationSegment {
  constellation: string
  points: [[number, number], [number, number]]
}

export interface SkyCatalog {
  schemaVersion: number
  frame: string
  deepSky: SkyCatalogSource[]
  brightStars: SkyCatalogSource[]
  constellationSegments: SkyConstellationSegment[]
  constellations: SkyCatalogSource[]
  counts: {
    deepSky: number
    brightStars: number
    constellations: number
    constellationSegments: number
  }
  provenance: Record<string, string>
}

export const DEFAULT_SETTINGS: AnalysisSettings = {
  deepSky: { enabled: true, value: 75 },
  brightStars: { enabled: true, value: 60 },
  constellations: { enabled: false, value: 55 },
  catalogDepth: 'deep',
  labelDensity: 'sparse',
  deepSkyColor: '#69BE7A',
  brightStarColor: '#D4B953',
  constellationColor: '#A391BF',
  fontWeight: 500,
  highContrast: false,
  annotationOpacity: .85,
  annotationLineWidth: 1.25,
  annotationFontSize: 18,
  markerStyle: 'circle',
  starMagnitudeLimit: 12,
  includeCatalogOnly: false,
}

export const LAYER_LABELS: Record<LayerKey, string> = {
  deepSky: '深空天体',
  brightStars: '恒星',
  constellations: '星座',
}
