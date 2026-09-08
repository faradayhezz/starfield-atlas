import type { AnalysisResult, AnalysisSettings, ImageMetadata } from './types'

const loadImage = (source: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const image = new Image()
    if (/^https?:/.test(source)) image.crossOrigin = 'anonymous'
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('无法读取用于导出的图像'))
    image.src = source
  })

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
