import { useEffect, useMemo, useRef, useState } from 'react'
import { getSkyCatalog, getSkyMapManifest } from '../api'
import type {
  AnalysisResult,
  HipsSurveyManifest,
  SkyCatalog,
  SkyCoordinate,
  SkyMapLayerManifest,
  SkyMapManifest,
} from '../types'

interface SkyMapDialogProps {
  result: AnalysisResult
  onClose: () => void
}

interface DomePosition {
  raDeg: number
  decDeg: number
  fovDeg: number
}

interface ProjectedSkyOverlay {
  constellationPath: string
  photoFillPoints?: string
  photoStrokePath: string
}

interface AladinCatalog {
  addSources: (sources: unknown[] | unknown) => void
  reportChange?: () => void
}

interface AladinViewer {
  addCatalog: (catalog: AladinCatalog) => void
  getFov: () => [number, number]
  getRaDec: () => [number, number]
  gotoRaDec: (raDeg: number, decDeg: number) => void
  increaseZoom: () => void
  on: (event: string, callback: () => void) => void
  removeLayers?: () => void
  setBaseImageLayer: (survey: unknown) => void
  setFoV: (fovDeg: number) => void
  setFoVRange: (minimumFovDeg: number, maximumFovDeg: number) => void
  world2pix: (raDeg: number, decDeg: number) => [number, number] | undefined
}

type AladinApi = typeof import('aladin-lite')['default']

type LayerId = SkyMapLayerManifest['id']

interface DomeLayer {
  id: LayerId
  shortTitle: string
  title: string
  description: string
  surveyId: HipsSurveyManifest['id']
  fallback: HipsSurveyManifest
}

const DOME_LAYERS: DomeLayer[] = [
  {
    id: 'filled',
    shortTitle: '全天光学',
    title: 'DSS2 全天彩色光学',
    description: '全天一致的可见光底图，放大后自动读取原生高阶 HiPS 瓦片',
    surveyId: 'dss2-color',
    fallback: { id: 'dss2-color', title: 'DSS2 全天彩色光学', url: '/api/sky-map/hips/dss2-color', maxOrder: 9, tileFormat: 'jpg', coverageFraction: 1, bundledOverview: false },
  },
  {
    id: 'ls-dr11',
    shortTitle: 'Legacy',
    title: 'DESI Legacy Surveys 高清光学',
    description: 'Legacy Surveys 原生光学覆盖；未观测区域保持为空',
    surveyId: 'legacy-dr10',
    fallback: { id: 'legacy-dr10', title: 'DESI Legacy Surveys DR10 彩色光学', url: '/api/sky-map/hips/legacy-dr10', maxOrder: 11, tileFormat: 'png', coverageFraction: 0.67339, bundledOverview: true },
  },
  {
    id: '2mass-color',
    shortTitle: '2MASS',
    title: '2MASS J/H/Ks 全天近红外',
    description: 'NASA/IPAC 2MASS 全天近红外科学影像',
    surveyId: '2mass-color',
    fallback: { id: '2mass-color', title: '2MASS J/H/Ks 全天近红外', url: '/api/sky-map/hips/2mass-color', maxOrder: 9, tileFormat: 'jpg', coverageFraction: 1, bundledOverview: true },
  },
]

const wrapRa = (value: number) => ((value % 360) + 360) % 360
const firstPersonMaxFov = (viewportWidth: number, viewportHeight: number) => {
  const aspect = viewportWidth / Math.max(1, viewportHeight)
  const cornerLimit = 65 * Math.PI / 180
  return 2 * Math.atan(Math.tan(cornerLimit) / Math.sqrt(1 + 1 / (aspect * aspect))) * 180 / Math.PI
}

const vectorFromSky = (point: SkyCoordinate): [number, number, number] => {
  const ra = point.raDeg * Math.PI / 180
  const dec = point.decDeg * Math.PI / 180
  const cosDec = Math.cos(dec)
  return [cosDec * Math.cos(ra), cosDec * Math.sin(ra), Math.sin(dec)]
}

const skyFromVector = (vector: [number, number, number]): SkyCoordinate => {
  const length = Math.hypot(...vector) || 1
  const [x, y, z] = vector.map((value) => value / length) as [number, number, number]
  return {
    raDeg: wrapRa(Math.atan2(y, x) * 180 / Math.PI),
    decDeg: Math.asin(Math.max(-1, Math.min(1, z))) * 180 / Math.PI,
  }
}

const interpolateGreatCircle = (start: SkyCoordinate, end: SkyCoordinate, steps = 10) => {
  const a = vectorFromSky(start)
  const b = vectorFromSky(end)
  const dot = Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
  const angle = Math.acos(dot)
  if (angle < 1e-7) return [start]
  const denominator = Math.sin(angle)
  return Array.from({ length: steps }, (_, index) => {
    const t = index / steps
    const left = Math.sin((1 - t) * angle) / denominator
    const right = Math.sin(t * angle) / denominator
    return skyFromVector([
      a[0] * left + b[0] * right,
      a[1] * left + b[1] * right,
      a[2] * left + b[2] * right,
    ])
  })
}

const denseBoundaryPoints = (points: SkyCoordinate[]) => points.length > 12
  ? points
  : points.flatMap((point, index) => interpolateGreatCircle(point, points[(index + 1) % points.length]))

const angularSeparationDeg = (left: SkyCoordinate, right: SkyCoordinate) => {
  const toRadians = Math.PI / 180
  const leftDec = left.decDeg * toRadians
  const rightDec = right.decDeg * toRadians
  const cosine = Math.sin(leftDec) * Math.sin(rightDec)
    + Math.cos(leftDec) * Math.cos(rightDec) * Math.cos((left.raDeg - right.raDeg) * toRadians)
  return Math.acos(Math.max(-1, Math.min(1, cosine))) / toRadians
}

const spacedLabelIndices = (
  objects: Array<{ raDeg?: number, decDeg?: number }>,
  minimumSeparationDeg: number,
  limit: number,
) => {
  const selected: number[] = []
  objects.forEach((object, index) => {
    if (selected.length >= limit || object.raDeg === undefined || object.decDeg === undefined) return
    const candidate = { raDeg: object.raDeg, decDeg: object.decDeg }
    const clear = selected.every((selectedIndex) => {
      const other = objects[selectedIndex]
      return other.raDeg === undefined || other.decDeg === undefined
        || angularSeparationDeg(candidate, { raDeg: other.raDeg, decDeg: other.decDeg }) >= minimumSeparationDeg
    })
    if (clear) selected.push(index)
  })
  return new Set(selected)
}

const spacedLabelIndicesAgainst = (
  objects: Array<{ raDeg?: number, decDeg?: number }>,
  minimumSeparationDeg: number,
  limit: number,
  occupied: SkyCoordinate[],
  eligible: (object: { raDeg?: number, decDeg?: number }, index: number) => boolean = () => true,
) => {
  const selected = new Set<number>()
  objects.forEach((object, index) => {
    if (
      selected.size >= limit
      || object.raDeg === undefined
      || object.decDeg === undefined
      || !eligible(object, index)
    ) return
    const candidate = { raDeg: object.raDeg, decDeg: object.decDeg }
    if (occupied.every((other) => angularSeparationDeg(candidate, other) >= minimumSeparationDeg)) {
      selected.add(index)
      occupied.push(candidate)
    }
  })
  return selected
}

const fitFootprintFov = (
  points: SkyCoordinate[],
  center: SkyCoordinate,
  viewportAspect: number,
  fallback: number,
) => {
  if (!points.length) return fallback
  const ra0 = center.raDeg * Math.PI / 180
  const dec0 = center.decDeg * Math.PI / 180
  let maxX = 0
  let maxY = 0
  for (const point of points) {
    const ra = point.raDeg * Math.PI / 180
    const dec = point.decDeg * Math.PI / 180
    const deltaRa = ra - ra0
    const denominator = Math.sin(dec0) * Math.sin(dec) + Math.cos(dec0) * Math.cos(dec) * Math.cos(deltaRa)
    if (denominator <= 0.02) return fallback
    const x = Math.cos(dec) * Math.sin(deltaRa) / denominator
    const y = (Math.cos(dec0) * Math.sin(dec) - Math.sin(dec0) * Math.cos(dec) * Math.cos(deltaRa)) / denominator
    maxX = Math.max(maxX, Math.abs(x))
    maxY = Math.max(maxY, Math.abs(y))
  }
  const tangentHalfWidth = Math.max(maxX, maxY * Math.max(.25, viewportAspect)) * 1.1
  return Math.max(fallback, 2 * Math.atan(tangentHalfWidth) * 180 / Math.PI)
}

function MapIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3.5 5.5 5-2.4 7 2.4 5-2.4v15.4l-5 2.4-7-2.4-5 2.4V5.5Z" /><path d="M8.5 3.1v15.4m7-13v15.4" /></svg>
}

function CloseMapIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
}

function RecenterIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2" /><path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3" /></svg>
}

function PlusIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
}

function MinusIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" /></svg>
}

export function SkyMapDialog({ result, onClose }: SkyMapDialogProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<AladinViewer | null>(null)
  const aladinApiRef = useRef<AladinApi | null>(null)
  const catalogsRef = useRef<AladinCatalog[]>([])
  const closeRef = useRef<HTMLButtonElement>(null)
  const viewFovRef = useRef(60)
  const fittedInitialFovRef = useRef(60)
  const maxFovRef = useRef(108)
  const [manifest, setManifest] = useState<SkyMapManifest>()
  const [skyCatalog, setSkyCatalog] = useState<SkyCatalog>()
  const [selectedLayerId, setSelectedLayerId] = useState<LayerId>('filled')
  const [viewerReady, setViewerReady] = useState(false)
  const [loadError, setLoadError] = useState<string>()
  const [position, setPosition] = useState<DomePosition>()
  const [projectedSkyOverlay, setProjectedSkyOverlay] = useState<ProjectedSkyOverlay>()
  const wcs = result.wcs
  const centerRaDeg = wcs.centerRaDeg
  const centerDecDeg = wcs.centerDecDeg
  const footprint = useMemo(() => wcs.frameBoundary?.length ? wcs.frameBoundary : wcs.frameCorners, [wcs.frameBoundary, wcs.frameCorners])
  // A first-person sky view behaves like a real wide-angle camera: it starts
  // near the photo's own field instead of backing out to an all-sky globe.
  const initialFov = useMemo(() => Math.min(90, Math.max(
    55,
    (wcs.horizontalFovDeg ?? 40) * 1.2,
    (wcs.verticalFovDeg ?? 30) * 1.2,
  )), [wcs.horizontalFovDeg, wcs.verticalFovDeg])
  const activeLayer = DOME_LAYERS.find((layer) => layer.id === selectedLayerId) ?? DOME_LAYERS[0]
  const activeSurvey = manifest?.hips?.surveys.find((survey) => survey.id === activeLayer.surveyId) ?? activeLayer.fallback

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([getSkyMapManifest(controller.signal), getSkyCatalog(controller.signal)])
      .then(([mapManifest, catalog]) => {
        setManifest(mapManifest)
        setSkyCatalog(catalog)
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setLoadError(caught instanceof Error ? caught.message : '无法读取内置天球资料')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [onClose])

  useEffect(() => {
    if (!containerRef.current || !manifest || !skyCatalog || centerRaDeg === undefined || centerDecDeg === undefined) return
    let cancelled = false
    let pollTimer: number | undefined
    let resizeObserver: ResizeObserver | undefined
    const container = containerRef.current

    void import('aladin-lite').then(async ({ default: Aladin }) => {
      aladinApiRef.current = Aladin
      await Aladin.init
      if (cancelled) return
      const denseFootprint = denseBoundaryPoints(footprint ?? [])
      const viewportAspect = container.clientWidth / Math.max(1, container.clientHeight)
      let maxFirstPersonFov = firstPersonMaxFov(container.clientWidth, container.clientHeight)
      maxFovRef.current = maxFirstPersonFov
      const fittedInitialFov = Math.min(maxFirstPersonFov, fitFootprintFov(
        denseFootprint,
        { raDeg: centerRaDeg, decDeg: centerDecDeg },
        viewportAspect,
        initialFov,
      ))
      const viewer = Aladin.aladin(container, {
        target: `${centerRaDeg} ${centerDecDeg}`,
        fov: fittedInitialFov,
        projection: 'TAN',
        cooFrame: 'equatorial',
        showReticle: false,
        showCooGrid: true,
        showCooGridControl: false,
        showFrame: false,
        showFov: false,
        showCooLocation: false,
        showZoomControl: false,
        showFullscreenControl: false,
        showLayersControl: false,
        showGotoControl: false,
        showProjectionControl: false,
        showSimbadPointerControl: false,
        showContextMenu: false,
        backgroundColor: '#02070b',
        gridColor: '#4cb5c5',
        gridOpacity: 0.28,
        gridOptions: { showLabels: true, thickness: 1 },
        mode: 'dark',
      }) as AladinViewer
      viewerRef.current = viewer
      viewer.setFoVRange(1 / 36000, maxFirstPersonFov)
      viewer.gotoRaDec(centerRaDeg, centerDecDeg)
      viewer.setFoV(fittedInitialFov)

      // Aladin finalises its WebGL canvas size after construction.  Wait for
      // two paint frames, then re-apply the camera before pixel-fit checks.
      await new Promise<void>((resolve) => window.requestAnimationFrame(
        () => window.requestAnimationFrame(() => resolve()),
      ))
      if (cancelled) return
      viewer.gotoRaDec(centerRaDeg, centerDecDeg)
      viewer.setFoV(fittedInitialFov)
      fittedInitialFovRef.current = fittedInitialFov
      viewFovRef.current = fittedInitialFov

      const photoObjects = result.objects.filter((object) => object.raDeg !== undefined && object.decDeg !== undefined && object.category === 'deepSky')
      const photoLabelSubset = photoObjects.slice(0, 80)
      const photoObjectCoordinates = new Set(photoObjects.map((object) => `${(object.raDeg as number).toFixed(3)}:${(object.decDeg as number).toFixed(3)}`))
      const mediumDeepSkyLabels = spacedLabelIndices(skyCatalog.deepSky, 3, 96)
      const mediumPhotoLabels = spacedLabelIndices(photoLabelSubset, 3, 16)
      const closePhotoLabels = spacedLabelIndices(photoLabelSubset, 1.5, 28)
      const detailPhotoLabels = spacedLabelIndices(photoLabelSubset, .65, 50)

      // Wide sky views share one occupied-coordinate pool across every label
      // catalog.  This preserves the most useful labels in priority order and
      // prevents cross-catalog collisions such as M31/仙女座 or 五车二/御夫座.
      const makeWideLabelSets = (mobile: boolean) => {
        const occupied: SkyCoordinate[] = []
        const photo = spacedLabelIndicesAgainst(
          photoLabelSubset,
          mobile ? 18 : 12,
          mobile ? 4 : 6,
          occupied,
        )
        const deepSky = spacedLabelIndicesAgainst(
          skyCatalog.deepSky,
          mobile ? 24 : 8,
          mobile ? 6 : 32,
          occupied,
          (object) => {
            const item = object as SkyCatalog['deepSky'][number]
            const coordinateKey = `${Number(item.raDeg).toFixed(3)}:${Number(item.decDeg).toFixed(3)}`
            return Number(item.priority ?? 0) >= 142 && !photoObjectCoordinates.has(coordinateKey)
          },
        )
        const constellation = spacedLabelIndicesAgainst(
          skyCatalog.constellations,
          mobile ? 24 : 12,
          mobile ? 8 : 24,
          occupied,
          (object) => Number((object as SkyCatalog['constellations'][number]).rank ?? 3) <= 1,
        )
        const star = spacedLabelIndicesAgainst(
          skyCatalog.brightStars,
          mobile ? 24 : 8,
          mobile ? 6 : 28,
          occupied,
          (object) => Number((object as SkyCatalog['brightStars'][number]).magnitude ?? 99) <= 1.5,
        )
        return { photo, deepSky, constellation, star }
      }
      const desktopWideLabels = makeWideLabelSets(false)
      const mobileWideLabels = makeWideLabelSets(true)

      const constellationCatalog = Aladin.catalog({
        name: '星座', shape: 'plus', color: '#9aa5ef', sourceSize: 6, displayLabel: true, labelColumn: 'label', labelColor: '#aeb8ff',
        labelFont: '650 12px Inter, "Microsoft YaHei", sans-serif',
        filter: (source: { data: { rank?: number, skyIndex?: number } }) => {
          const fov = viewFovRef.current
          const rank = Number(source.data.rank ?? 3)
          const index = Number(source.data.skyIndex ?? Number.MAX_SAFE_INTEGER)
          if (container.clientWidth < 600) return fov > 40 ? mobileWideLabels.constellation.has(index) : fov > 20 ? rank <= 2 : rank <= 3
          return fov > 70 ? desktopWideLabels.constellation.has(index) : fov > 32 ? rank <= 2 : rank <= 3
        },
      }) as AladinCatalog
      constellationCatalog.addSources(skyCatalog.constellations.map((item, skyIndex) => Aladin.source(item.raDeg, item.decDeg, { ...item, skyIndex })))
      viewer.addCatalog(constellationCatalog)

      const starCatalog = Aladin.catalog({
        name: '亮星', shape: 'plus', color: '#ffd95a', sourceSize: 8, displayLabel: true, labelColumn: 'label', labelColor: '#ffe590',
        labelFont: '700 12px Inter, "Microsoft YaHei", sans-serif',
        filter: (source: { data: { magnitude?: number, skyIndex?: number } }) => {
          const fov = viewFovRef.current
          const magnitude = Number(source.data.magnitude ?? 99)
          const index = Number(source.data.skyIndex ?? Number.MAX_SAFE_INTEGER)
          if (container.clientWidth < 600) return fov > 40 ? mobileWideLabels.star.has(index) : magnitude <= (fov > 20 ? 2.5 : 4)
          return fov > 70 ? desktopWideLabels.star.has(index) : magnitude <= (fov > 30 ? 2.5 : 4)
        },
      }) as AladinCatalog
      starCatalog.addSources(skyCatalog.brightStars.map((item, skyIndex) => Aladin.source(item.raDeg, item.decDeg, { ...item, skyIndex })))
      viewer.addCatalog(starCatalog)

      const deepSkyCatalog = Aladin.catalog({
        name: '常规深空天体', shape: 'circle', color: '#35ef8b', sourceSize: 7, displayLabel: true, labelColumn: 'label', labelColor: '#79ffb7',
        labelFont: '700 12px Inter, "Microsoft YaHei", sans-serif', onClick: 'showPopup',
        filter: (source: { data: { raDeg?: number, decDeg?: number, priority?: number, skyIndex?: number } }) => {
          const fov = viewFovRef.current
          const priority = Number(source.data.priority ?? 0)
          const index = Number(source.data.skyIndex ?? Number.MAX_SAFE_INTEGER)
          const coordinateKey = `${Number(source.data.raDeg).toFixed(3)}:${Number(source.data.decDeg).toFixed(3)}`
          const minimumPriority = container.clientWidth < 600
            ? (fov > 40 ? 142 : fov > 20 ? 122 : fov > 10 ? 92 : 0)
            : (fov > 70 ? 142 : fov > 32 ? 122 : fov > 12 ? 92 : 0)
          const spacingAllows = container.clientWidth < 600 && fov > 40
            ? mobileWideLabels.deepSky.has(index)
            : fov > 70 ? desktopWideLabels.deepSky.has(index)
              : fov > 32 ? mediumDeepSkyLabels.has(index)
                : true
          return !photoObjectCoordinates.has(coordinateKey) && priority >= minimumPriority && spacingAllows
        },
      }) as AladinCatalog
      deepSkyCatalog.addSources(skyCatalog.deepSky.map((item, skyIndex) => Aladin.source(item.raDeg, item.decDeg, { ...item, skyIndex })))
      viewer.addCatalog(deepSkyCatalog)

      let photoMarkerCatalog: AladinCatalog | undefined
      let photoLabelCatalog: AladinCatalog | undefined
      if (photoObjects.length) {
        photoMarkerCatalog = Aladin.catalog({
          name: '照片视场内深空天体', shape: 'circle', color: '#25ff72', sourceSize: 9, onClick: 'showPopup',
          filter: (source: { data: { photoIndex?: number } }) => {
            const fov = viewFovRef.current
            const index = Number(source.data.photoIndex ?? Number.MAX_SAFE_INTEGER)
            if (container.clientWidth < 600) {
              return index < (fov > 50 ? 40 : fov > 25 ? 100 : fov > 12 ? 240 : photoObjects.length)
            }
            return index < (fov > 90 ? 80 : fov > 50 ? 240 : fov > 25 ? 480 : photoObjects.length)
          },
        }) as AladinCatalog
        const photoSources = photoObjects.map((object, index) => Aladin.source(object.raDeg as number, object.decDeg as number, {
          ...object,
          photoIndex: index,
          popupTitle: object.label,
          popupDesc: object.type ?? '照片视场内的深空天体',
        }))
        photoMarkerCatalog.addSources(photoSources)
        viewer.addCatalog(photoMarkerCatalog)

        photoLabelCatalog = Aladin.catalog({
          name: '照片视场重点标签', shape: 'circle', color: '#25ff72', sourceSize: 9, displayLabel: true,
          labelColumn: 'label', labelColor: '#c5ffdc', labelFont: '800 12px Inter, "Microsoft YaHei", sans-serif',
          filter: (source: { data: { photoIndex?: number } }) => {
            const fov = viewFovRef.current
            const index = Number(source.data.photoIndex ?? 999)
            return container.clientWidth < 600 && fov > 40 ? mobileWideLabels.photo.has(index)
              : fov > 70 ? desktopWideLabels.photo.has(index)
              : fov > 50 ? mediumPhotoLabels.has(index)
                : fov > 25 ? closePhotoLabels.has(index)
                  : fov > 12 ? detailPhotoLabels.has(index)
                    : index < 80
          },
        }) as AladinCatalog
        photoLabelCatalog.addSources(photoLabelSubset.map((object, index) => Aladin.source(object.raDeg as number, object.decDeg as number, {
          ...object,
          photoIndex: index,
        })))
        viewer.addCatalog(photoLabelCatalog)
      }

      catalogsRef.current = [
        constellationCatalog,
        starCatalog,
        deepSkyCatalog,
        ...(photoMarkerCatalog ? [photoMarkerCatalog] : []),
        ...(photoLabelCatalog ? [photoLabelCatalog] : []),
      ]
      let lastOverlayUpdate = 0
      const updateProjectedSky = (raDeg: number, decDeg: number, horizontalFov: number) => {
        const now = performance.now()
        if (now - lastOverlayUpdate < 70) return
        lastOverlayUpdate = now
        const reasonableLimit = Math.max(container.clientWidth, container.clientHeight) * 8
        const projectSafely = (point: SkyCoordinate) => {
          try {
            const pixel = viewer.world2pix(point.raDeg, point.decDeg)
            if (
              !pixel
              || !Number.isFinite(pixel[0])
              || !Number.isFinite(pixel[1])
              || Math.abs(pixel[0]) > reasonableLimit
              || Math.abs(pixel[1]) > reasonableLimit
            ) return undefined
            return pixel
          } catch {
            return undefined
          }
        }
        const pixels = denseFootprint.map(projectSafely)
        let photoStrokePath = ''
        for (let index = 0; index < pixels.length; index += 1) {
          const start = pixels[index]
          const end = pixels[(index + 1) % pixels.length]
          if (start && end) photoStrokePath += `M${start[0].toFixed(1)} ${start[1].toFixed(1)}L${end[0].toFixed(1)} ${end[1].toFixed(1)}`
        }
        const complete = pixels.every((pixel) => pixel !== undefined)
        const validPixels = pixels.filter((pixel): pixel is [number, number] => pixel !== undefined)
        const intersectsViewport = validPixels.length > 0
          && Math.max(...validPixels.map((pixel) => pixel[0])) >= 0
          && Math.min(...validPixels.map((pixel) => pixel[0])) <= container.clientWidth
          && Math.max(...validPixels.map((pixel) => pixel[1])) >= 0
          && Math.min(...validPixels.map((pixel) => pixel[1])) <= container.clientHeight
        const viewCenter = { raDeg, decDeg }
        const segmentLimit = Math.min(88, Math.max(38, horizontalFov * .72 + 18))
        let constellationPath = ''
        skyCatalog.constellationSegments.forEach((segment) => {
          for (let index = 0; index < segment.points.length - 1; index += 1) {
            const startPoint = { raDeg: segment.points[index][0], decDeg: segment.points[index][1] }
            const endPoint = { raDeg: segment.points[index + 1][0], decDeg: segment.points[index + 1][1] }
            if (
              angularSeparationDeg(viewCenter, startPoint) > segmentLimit
              && angularSeparationDeg(viewCenter, endPoint) > segmentLimit
            ) continue
            const start = projectSafely(startPoint)
            const end = projectSafely(endPoint)
            if (start && end) constellationPath += `M${start[0].toFixed(1)} ${start[1].toFixed(1)}L${end[0].toFixed(1)} ${end[1].toFixed(1)}`
          }
        })
        setProjectedSkyOverlay(photoStrokePath || constellationPath ? {
          constellationPath,
          photoStrokePath,
          photoFillPoints: complete && intersectsViewport
            ? validPixels.map((pixel) => `${pixel[0].toFixed(1)},${pixel[1].toFixed(1)}`).join(' ')
            : undefined,
        } : undefined)
      }
      const updatePosition = () => {
        const [raDeg, decDeg] = viewer.getRaDec()
        let [horizontalFov] = viewer.getFov()
        if (horizontalFov > maxFirstPersonFov + .05) {
          viewer.setFoV(maxFirstPersonFov)
          horizontalFov = maxFirstPersonFov
        }
        viewFovRef.current = horizontalFov
        setPosition({ raDeg: wrapRa(raDeg), decDeg, fovDeg: horizontalFov })
        updateProjectedSky(raDeg, decDeg, horizontalFov)
        catalogsRef.current.forEach((catalog) => catalog.reportChange?.())
      }
      viewer.on('positionChanged', updatePosition)
      viewer.on('zoomChanged', updatePosition)
      resizeObserver = new ResizeObserver(() => {
        maxFirstPersonFov = firstPersonMaxFov(container.clientWidth, container.clientHeight)
        maxFovRef.current = maxFirstPersonFov
        viewer.setFoVRange(1 / 36000, maxFirstPersonFov)
        const [currentFov] = viewer.getFov()
        if (currentFov > maxFirstPersonFov) viewer.setFoV(maxFirstPersonFov)
        updatePosition()
      })
      resizeObserver.observe(container)
      pollTimer = window.setInterval(updatePosition, 350)
      updatePosition()
      setViewerReady(true)
    }).catch((caught: unknown) => {
      if (!cancelled) setLoadError(caught instanceof Error ? caught.message : '当前设备无法启动 WebGL2 天球')
    })

    return () => {
      cancelled = true
      if (pollTimer !== undefined) window.clearInterval(pollTimer)
      resizeObserver?.disconnect()
      viewerRef.current?.removeLayers?.()
      viewerRef.current = null
      aladinApiRef.current = null
      catalogsRef.current = []
      container.replaceChildren()
      setViewerReady(false)
      setProjectedSkyOverlay(undefined)
    }
  }, [centerDecDeg, centerRaDeg, footprint, initialFov, manifest, result.objects, skyCatalog])

  useEffect(() => {
    const Aladin = aladinApiRef.current
    if (!viewerReady || !viewerRef.current || !Aladin) return
    let cancelled = false
    const controller = new AbortController()
    const activateSurvey = async () => {
      if (activeSurvey.bundledOverview === false) {
        const timer = window.setTimeout(() => controller.abort(), 4500)
        try {
          const response = await fetch(`${activeSurvey.url}/properties`, { signal: controller.signal })
          if (!response.ok) throw new Error(`HiPS ${response.status}`)
        } catch {
          if (!cancelled) setSelectedLayerId('2mass-color')
          return
        } finally {
          window.clearTimeout(timer)
        }
      }
      if (cancelled || !viewerRef.current) return
      const survey = Aladin.imageHiPS(activeSurvey.url, {
        name: activeSurvey.title,
        url: activeSurvey.url,
        cooFrame: 'equatorial',
        maxOrder: activeSurvey.maxOrder,
        imgFormat: activeSurvey.tileFormat === 'jpg' ? 'jpeg' : activeSurvey.tileFormat,
      })
      viewerRef.current.setBaseImageLayer(survey)
    }
    void activateSurvey()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [activeSurvey, viewerReady])

  const recenter = () => {
    if (!viewerRef.current || centerRaDeg === undefined || centerDecDeg === undefined) return
    viewerRef.current.gotoRaDec(centerRaDeg, centerDecDeg)
    viewerRef.current.setFoV(fittedInitialFovRef.current)
  }

  const zoomOut = () => {
    if (!viewerRef.current) return
    const [currentFov] = viewerRef.current.getFov()
    viewerRef.current.setFoV(Math.min(maxFovRef.current, currentFov * 1.35))
  }

  const gotoPole = (decDeg: number) => {
    if (!viewerRef.current) return
    viewerRef.current.gotoRaDec(position?.raDeg ?? centerRaDeg ?? 0, decDeg)
    viewerRef.current.setFoV(Math.min(60, viewFovRef.current))
  }

  const hasSolution = centerRaDeg !== undefined && centerDecDeg !== undefined && Boolean(footprint?.length)
  const coverageNote = selectedLayerId === 'ls-dr11'
    ? 'Legacy DR10 光学 HiPS 当前覆盖约 67.3%；空白表示该巡天未观测'
    : selectedLayerId === '2mass-color'
      ? '2MASS J/H/Ks 近红外全天观测；颜色是科学波段合成，并非肉眼自然色'
      : 'DSS2 全天光学底图；放大后自动读取原生高阶瓦片，不再拉伸低清概览'

  return (
    <div className="sky-map-backdrop sky-map-backdrop--immersive" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="sky-map-dialog sky-map-dialog--dome sky-map-dialog--immersive" role="dialog" aria-modal="true" aria-labelledby="sky-map-title">
        <header className="sky-map-header">
          <div className="sky-map-title-group">
            <span className="sky-map-brand"><MapIcon /></span>
            <div><h2 id="sky-map-title">天空视野定位</h2><p>站在星空中央 · 拖动视线环顾全天</p></div>
          </div>
          <div className="sky-map-header-actions">
            <div className="sky-map-source-toggle is-active" aria-label="高清天空状态">
              <span><i />真实巡天影像 · 高清瓦片</span>
              <small>全天概览内置 · 当前视区按需缓存</small>
            </div>
            <button ref={closeRef} className="sky-map-close" type="button" onClick={onClose} aria-label="关闭天空视野"><CloseMapIcon /></button>
          </div>
        </header>

        <div className="sky-map-stage sky-map-stage--dome sky-map-stage--first-person">
          <div ref={containerRef} className="sky-map-canvas sky-map-canvas--dome" aria-label="第一人称可连续环顾的真实天空" />
          {projectedSkyOverlay && <svg className="sky-map-photo-overlay" aria-hidden="true">
            <path className="is-constellation" d={projectedSkyOverlay.constellationPath} />
            {projectedSkyOverlay.photoFillPoints && <polygon points={projectedSkyOverlay.photoFillPoints} />}
            <path className="is-photo" d={projectedSkyOverlay.photoStrokePath} />
          </svg>}
          {!hasSolution && <div className="sky-map-empty"><MapIcon /><h3>没有可绘制的精确视场</h3><p>请重新识别照片以生成四边天球边界。</p></div>}
          {loadError && <div className="sky-map-empty"><h3>内置天球未就绪</h3><p>{loadError}</p></div>}

          <div className="sky-map-readout" aria-live="polite">
            <span>当前视线</span>
            <strong>RA {(position?.raDeg ?? centerRaDeg ?? 0).toFixed(4)}°</strong>
            <strong>Dec {(position?.decDeg ?? centerDecDeg ?? 0).toFixed(4)}°</strong>
            <small>FOV {(position?.fovDeg ?? initialFov).toFixed(1)}°</small>
          </div>

          <div className="sky-map-controls" aria-label="天空视野控制">
            <button type="button" onClick={() => viewerRef.current?.increaseZoom()} aria-label="放大星空"><PlusIcon /></button>
            <button type="button" onClick={zoomOut} aria-label="缩小星空"><MinusIcon /></button>
            <button type="button" onClick={() => gotoPole(89.5)} aria-label="查看北天极"><span className="sky-map-pole-label">北</span></button>
            <button type="button" onClick={() => gotoPole(-89.5)} aria-label="查看南天极"><span className="sky-map-pole-label">南</span></button>
            <button type="button" onClick={recenter} aria-label="重新定位照片视场"><RecenterIcon /></button>
          </div>

          <div className="sky-map-layer-switch" role="group" aria-label="天空影像数据源">
            {DOME_LAYERS.map((layer) => (
              <button key={layer.id} type="button" className={selectedLayerId === layer.id ? 'is-active' : ''} aria-pressed={selectedLayerId === layer.id} title={layer.description} onClick={() => setSelectedLayerId(layer.id)}>
                <span>{layer.shortTitle}</span>
                {layer.id === 'filled' && <small>推荐</small>}
              </button>
            ))}
          </div>

          <div className="sky-map-field-card">
            <span><i />当前照片视场</span>
            <strong>{wcs.horizontalFovDeg?.toFixed(2) ?? '—'}° × {wcs.verticalFovDeg?.toFixed(2) ?? '—'}°</strong>
            <small>旋转 {wcs.rollDeg?.toFixed(2) ?? '—'}° · J2000</small>
          </div>

          <div className="sky-map-drag-hint"><span>↔</span> 拖动环顾天空 · 滚轮或双指缩放</div>
          <div className="sky-map-marker-key" aria-label="天体标注图例"><span className="is-star">亮星</span><span className="is-constellation">星座</span><span className="is-dso">深空天体</span></div>
          <div className="sky-map-coverage-note">{coverageNote}</div>
        </div>

        <footer className="sky-map-footer">
          <div><span>{activeLayer.title}</span><span>HiPS order 0–{activeSurvey.maxOrder} · 自动分层</span></div>
          <div className="sky-map-credit">
            <span>图像：</span>
            {selectedLayerId === 'filled' && <a href="https://archive.stsci.edu/dss/" target="_blank" rel="noreferrer">DSS2 / STScI · Caltech · AAO</a>}
            {selectedLayerId === 'ls-dr11' && <a href="https://www.legacysurvey.org/acknowledgment/" target="_blank" rel="noreferrer">DESI Legacy Surveys / D. Lang · CC BY 4.0</a>}
            {selectedLayerId === '2mass-color' && <a href="https://irsa.ipac.caltech.edu/Missions/2mass.html" target="_blank" rel="noreferrer">2MASS / UMass · IPAC/Caltech · NASA · NSF</a>}
            <a className="sky-map-official-link" href="https://aladin.cds.unistra.fr/AladinLite/" target="_blank" rel="noreferrer">Aladin Lite / CDS</a>
          </div>
        </footer>
      </section>
    </div>
  )
}
