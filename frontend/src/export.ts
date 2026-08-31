import type { AnalysisResult, AnalysisSettings, DetectedObject, ImageMetadata } from './types'

const DEFAULT_COLORS = {
  deepSky: '#18df69',
  brightStars: '#f4ce3a',
  constellations: '#b86ae6',
}

const resolveCoordinate = (value: number | undefined, extent: number): number | undefined => {
  if (value === undefined) return undefined
  return Math.abs(value) <= 1 ? value * extent : value
}

const loadImage = (source: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const image = new Image()
    if (/^https?:/.test(source)) image.crossOrigin = 'anonymous'
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('无法读取用于导出的图像'))
    image.src = source
  })

function drawObject(context: CanvasRenderingContext2D, object: DetectedObject, width: number, height: number, settings?: AnalysisSettings) {
  const color = settings
    ? object.category === 'deepSky'
      ? settings.deepSkyColor
      : object.category === 'brightStars'
        ? settings.brightStarColor
        : settings.constellationColor
    : DEFAULT_COLORS[object.category]
  const highContrast = settings?.highContrast ?? true
  const fontWeight = settings?.fontWeight ?? 650
  const markerLineWidth = Math.max(2, width / 1500)
  const contrastExtra = Math.max(3, width / 1800)
  context.save()
  if (object.category === 'constellations' && settings) context.globalAlpha = Math.max(.2, Math.min(1, settings.constellations.value / 100))
  context.strokeStyle = color
  context.fillStyle = color
  context.lineWidth = markerLineWidth
  context.shadowColor = 'rgba(0,0,0,.9)'
  context.shadowBlur = highContrast ? Math.max(3, width / 800) : Math.max(1, width / 1400)
  context.lineJoin = 'round'

  object.lines?.forEach((line) => {
    const strokeLine = (strokeStyle: string, lineWidth: number) => {
      context.beginPath()
      line.forEach((point, index) => {
        const x = resolveCoordinate(point.x, width) ?? 0
        const y = resolveCoordinate(point.y, height) ?? 0
        if (index === 0) context.moveTo(x, y)
        else context.lineTo(x, y)
      })
      context.strokeStyle = strokeStyle
      context.lineWidth = lineWidth
      context.stroke()
    }
    if (highContrast) strokeLine('rgba(2, 4, 5, .94)', markerLineWidth + contrastExtra)
    strokeLine(color, markerLineWidth)
  })

  const x = resolveCoordinate(object.x, width)
  const y = resolveCoordinate(object.y, height)
  if (x === undefined || y === undefined) {
    context.restore()
    return
  }
  const radius = object.radius && object.radius <= 1 ? object.radius * Math.min(width, height) : object.radius
  const markerRadius = radius ?? (object.category === 'deepSky' ? Math.max(18, width / 100) : Math.max(7, width / 350))
  if (highContrast) {
    context.beginPath()
    context.arc(x, y, markerRadius, 0, Math.PI * 2)
    context.strokeStyle = 'rgba(2, 4, 5, .96)'
    context.lineWidth = markerLineWidth + contrastExtra
    context.stroke()
  }
  context.beginPath()
  context.arc(x, y, markerRadius, 0, Math.PI * 2)
  context.strokeStyle = color
  context.lineWidth = markerLineWidth
  context.stroke()
  if (object.category === 'brightStars') {
    const dotRadius = Math.max(3, width / 900)
    if (highContrast) {
      context.beginPath()
      context.arc(x, y, dotRadius + Math.max(2, width / 2200), 0, Math.PI * 2)
      context.fillStyle = 'rgba(2, 4, 5, .96)'
      context.fill()
    }
    context.beginPath()
    context.arc(x, y, dotRadius, 0, Math.PI * 2)
    context.fillStyle = color
    context.fill()
  }
  const fontSize = Math.max(24, Math.round(width / 84))
  context.font = `${fontWeight} ${fontSize}px "Microsoft YaHei", "Noto Sans SC", sans-serif`
  context.textBaseline = 'middle'
  const labelX = resolveCoordinate(object.labelX, width) ?? x + markerRadius + fontSize * .35
  const labelY = resolveCoordinate(object.labelY, height) ?? y
  context.lineWidth = Math.max(4, fontSize / (highContrast ? 4.5 : 8))
  context.strokeStyle = highContrast ? 'rgba(2, 4, 5, .98)' : 'rgba(8, 11, 13, .76)'
  context.strokeText(object.label, labelX, labelY)
  context.fillStyle = color
  context.fillText(object.label, labelX, labelY)
  context.shadowBlur = 0
  context.restore()
}

export async function createAnnotatedBlob(
  source: string,
  objects: DetectedObject[],
  settings?: AnalysisSettings,
  coordinateSize?: Pick<ImageMetadata, 'width' | 'height'>,
): Promise<Blob> {
  const image = await loadImage(source)
  const canvas = document.createElement('canvas')
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  const context = canvas.getContext('2d')
  if (!context) throw new Error('浏览器无法创建导出画布')
  context.drawImage(image, 0, 0)
  const coordinateWidth = coordinateSize?.width ?? canvas.width
  const coordinateHeight = coordinateSize?.height ?? canvas.height
  context.save()
  context.scale(canvas.width / coordinateWidth, canvas.height / coordinateHeight)
  objects.forEach((object) => drawObject(context, object, coordinateWidth, coordinateHeight, settings))
  context.restore()
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('生成标注图失败')), 'image/png', .95)
  })
}

export async function sourceToBlob(source: string): Promise<Blob> {
  const response = await fetch(source)
  if (!response.ok) throw new Error('下载标注图失败')
  return response.blob()
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function exportResultJson(result: AnalysisResult, settings: AnalysisSettings) {
  const payload = {
    schemaVersion: '1.0',
    exportedAt: new Date().toISOString(),
    image: result.metadata,
    settings,
    astrometry: result.wcs,
    summary: {
      deepSky: result.objects.filter((object) => object.category === 'deepSky').length,
      brightStars: result.objects.filter((object) => object.category === 'brightStars').length,
      constellations: result.objects.filter((object) => object.category === 'constellations').length,
    },
    objects: result.objects.map((object) => Object.fromEntries(Object.entries(object).filter(([key]) => key !== 'raw'))),
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const base = result.metadata.filename.replace(/\.[^.]+$/, '') || 'starfield'
  downloadBlob(blob, `${base}-objects.json`)
}

export function getImageDimensions(source: string): Promise<Pick<ImageMetadata, 'width' | 'height'>> {
  return loadImage(source).then((image) => ({ width: image.naturalWidth, height: image.naturalHeight }))
}
