import { useEffect, useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent } from 'react'
import { annotationCoordinate, layoutOverlayObjects, markerGeometry, selectOverlayObjects } from '../overlay'
import type { AnalysisProgress, AnalysisResult, AnalysisSettings, DetectedObject } from '../types'
import { FitIcon, ZoomInIcon, ZoomOutIcon } from './Icons'

interface StarCanvasProps {
  result: AnalysisResult
  settings: AnalysisSettings
  source?: string
  renderOverlay: boolean
  selected?: DetectedObject
  progress?: AnalysisProgress
  onBrowse: () => void
  onFile: (file: File) => void
  onSelect: (object: DetectedObject) => void
}

function Annotation({ object, width, height, selected, settings, onSelect }: { object: DetectedObject; width: number; height: number; selected: boolean; settings: AnalysisSettings; onSelect: (object: DetectedObject) => void }) {
  const geometry = markerGeometry(object, width, height, settings)
  const { radius, lineWidth, fontSize } = geometry
  const x = geometry.x ?? 0
  const y = geometry.y ?? 0
  const color = object.category === 'deepSky' ? settings.deepSkyColor : object.category === 'brightStars' ? settings.brightStarColor : settings.constellationColor
  const corners = (r: number) => { const edge = r * .38; return `M ${x - r + edge} ${y - r} H ${x - r} V ${y - r + edge} M ${x + r - edge} ${y - r} H ${x + r} V ${y - r + edge} M ${x - r} ${y + r - edge} V ${y + r} H ${x - r + edge} M ${x + r} ${y + r - edge} V ${y + r} H ${x + r - edge}` }
  const labelX = annotationCoordinate(object.labelX, width) ?? x + radius + fontSize * .5
  const labelY = annotationCoordinate(object.labelY, height) ?? y
  const opacity = settings.annotationOpacity * (object.category === 'constellations' ? settings.constellations.value / 100 : 1)
  return <g className={`annotation annotation--${object.category}${selected ? ' is-selected' : ''}`} style={{ color, opacity: selected ? Math.max(opacity, .82) : opacity }} onClick={(event) => { event.stopPropagation(); onSelect({ ...object, label: object.label || object.name }) }}>
    <title>{object.label || object.name} · 星表坐标位置</title>
    {object.lines?.map((line, index) => <polyline key={index} points={line.map((point) => `${annotationCoordinate(point.x, width) ?? 0},${annotationCoordinate(point.y, height) ?? 0}`).join(' ')} fill="none" stroke="currentColor" strokeWidth={lineWidth} />)}
    {object.x !== undefined && object.y !== undefined && <>
      {settings.highContrast && (settings.markerStyle === 'corners' ? <path d={corners(radius)} fill="none" stroke="#090a0b" strokeWidth={lineWidth * 2.6} /> : <circle cx={x} cy={y} r={radius} fill="none" stroke="#090a0b" strokeWidth={lineWidth * 2.6} />)}
      {settings.markerStyle === 'corners' ? <path d={corners(radius)} fill="none" stroke="currentColor" strokeWidth={lineWidth} /> : <circle cx={x} cy={y} r={radius} fill="none" stroke="currentColor" strokeWidth={lineWidth} />}
      {selected && <path className="selection-corners" d={corners(radius + fontSize * .65)} fill="none" stroke="currentColor" strokeWidth={lineWidth} />}
      {object.label && <text x={labelX} y={labelY} dominantBaseline="middle" fontSize={fontSize} fontWeight={settings.fontWeight} fill="currentColor" stroke={settings.highContrast ? '#090a0b' : 'none'} strokeWidth={settings.highContrast ? fontSize * .18 : 0} paintOrder="stroke" strokeLinejoin="round">{object.label}</text>}
    </>}
  </g>
}

export function StarCanvas({ result, settings, source, renderOverlay, selected, progress, onSelect }: StarCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ pointerId: number; x: number; y: number; panX: number; panY: number } | undefined>(undefined)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [panning, setPanning] = useState(false)
  const [annotated, setAnnotated] = useState(true)
  const [viewport, setViewport] = useState({ width: 1, height: 1 })
  const [cursor, setCursor] = useState<{ x: number; y: number }>()
  const [previewSize, setPreviewSize] = useState<{ width: number; height: number }>()
  const width = result.metadata.width ?? 1920
  const height = result.metadata.height ?? 1280
  const fitScale = Math.min(viewport.width / width, viewport.height / height)
  const maskId = useId().replaceAll(':', '')
  const visibleObjects = useMemo(() => {
    const objects = selectOverlayObjects(result.objects, settings)
    if (selected && !objects.some((object) => object.id === selected.id)) objects.push(selected)
    return layoutOverlayObjects(objects, width, height, settings)
  }, [result.objects, settings, selected, width, height])
  const protectedCores = useMemo(() => [
    ...visibleObjects.filter((object) => object.category !== 'constellations' && object.x !== undefined && object.y !== undefined).map((object) => markerGeometry(object, width, height, settings)),
    ...visibleObjects.flatMap((object) => (object.protectedPoints ?? []).map((point) => ({ x: annotationCoordinate(point.x, width), y: annotationCoordinate(point.y, height), coreRadius: Math.max(3, 7 * width / 1920) }))),
  ], [visibleObjects, width, height, settings])
  const isReducedPreview = previewSize !== undefined && (previewSize.width < width || previewSize.height < height)
  const nativePreviewZoom = (previewSize?.width ?? width) / width / fitScale
  const actualPercent = Math.round(fitScale * zoom * width / (previewSize?.width ?? width) * 100)

  useEffect(() => {
    if (!canvasRef.current) return
    const observer = new ResizeObserver(([entry]) => setViewport({ width: Math.max(1, entry.contentRect.width - 24), height: Math.max(1, entry.contentRect.height - 24) }))
    observer.observe(canvasRef.current)
    return () => observer.disconnect()
  }, [])
  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }) }
  const changeZoom = (next: number) => {
    const clamped = Math.max(.25, Math.min(8 / Math.max(fitScale, .001), next))
    setPan((current) => ({ x: current.x * clamped / zoom, y: current.y * clamped / zoom }))
    setZoom(clamped)
  }
  useEffect(() => { resetView(); setAnnotated(true); setPreviewSize(undefined) }, [result.jobId, source])
  useEffect(() => {
    if (!selected || selected.x === undefined || selected.y === undefined) return
    const nextZoom = Math.max(zoom, 1.6)
    const x = annotationCoordinate(selected.x, width) ?? width / 2
    const y = annotationCoordinate(selected.y, height) ?? height / 2
    setZoom(nextZoom)
    setPan({ x: -(x - width / 2) * fitScale * nextZoom, y: -(y - height / 2) * fitScale * nextZoom })
    setAnnotated(true)
  }, [selected?.id])
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.target as Element)?.closest('input, textarea, select, [contenteditable="true"]') || document.querySelector('[role="dialog"]')) return
      if (event.ctrlKey || event.metaKey || event.altKey) return
      if (event.key === '0') { event.preventDefault(); resetView() }
      if (event.key === '1') { event.preventDefault(); changeZoom(nativePreviewZoom) }
      if (event.key === '+' || event.key === '=') { event.preventDefault(); changeZoom(zoom * 1.25) }
      if (event.key === '-') { event.preventDefault(); changeZoom(zoom / 1.25) }
      if (event.key.toLowerCase() === 'h') { event.preventDefault(); setAnnotated((value) => !value) }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [zoom, fitScale, nativePreviewZoom])
  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    if (!source || progress) return
    event.preventDefault()
    const rect = event.currentTarget.getBoundingClientRect()
    const next = Math.max(.25, Math.min(8 / fitScale, zoom * (event.deltaY < 0 ? 1.15 : 1 / 1.15)))
    const focalX = event.clientX - rect.left - rect.width / 2
    const focalY = event.clientY - rect.top - rect.height / 2
    setPan({ x: focalX - (focalX - pan.x) * next / zoom, y: focalY - (focalY - pan.y) * next / zoom })
    setZoom(next)
  }
  const pointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!source || progress || event.button !== 0 || (event.target as Element).closest('.annotation')) return
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y }
    setPanning(true)
  }
  const pointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - rect.left - rect.width / 2 - pan.x) / (fitScale * zoom) + width / 2
    const y = (event.clientY - rect.top - rect.height / 2 - pan.y) / (fitScale * zoom) + height / 2
    setCursor(x >= 0 && x <= width && y >= 0 && y <= height ? { x: Math.floor(x), y: Math.floor(y) } : undefined)
    const drag = dragRef.current
    if (drag?.pointerId === event.pointerId) setPan({ x: drag.panX + event.clientX - drag.x, y: drag.panY + event.clientY - drag.y })
  }
  const pointerEnd = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    dragRef.current = undefined
    setPanning(false)
  }
  return <section className="canvas-column" aria-label="照片工作区">
    <div className="canvas-toolbar"><div className="segmented-control" aria-label="照片显示"><button type="button" aria-pressed={!annotated} onClick={() => setAnnotated(false)}>原图</button><button type="button" aria-pressed={annotated} onClick={() => setAnnotated(true)}>标注</button></div><div className="canvas-view-tools"><button type="button" title="适应窗口（0）" onClick={resetView}><FitIcon /><span>适合窗口</span></button><button type="button" title={isReducedPreview ? "预览图像素 100%（1）；导出保持原始像素" : "原始像素 100%（1）"} onClick={() => changeZoom(nativePreviewZoom)}>{isReducedPreview ? '100% 预览' : '100%'}</button><button type="button" aria-label="缩小" onClick={() => changeZoom(zoom / 1.25)}><ZoomOutIcon /></button><button type="button" aria-label="放大" onClick={() => changeZoom(zoom * 1.25)}><ZoomInIcon /></button></div><span className="canvas-filename" title={result.metadata.filename}>{result.metadata.filename} <small>({width} × {height})</small></span></div>
    <div ref={canvasRef} className={`star-canvas ${source ? 'is-pannable' : ''} ${panning ? 'is-panning' : ''}`} onWheel={handleWheel} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd} onPointerCancel={pointerEnd} onPointerLeave={() => setCursor(undefined)} aria-describedby="canvas-help">
      <p id="canvas-help" className="visually-hidden">滚轮缩放，拖动平移。快捷键：0 适应窗口，1 原始像素，H 切换标注，加减号缩放。</p>
      {source ? <div className="image-stage" style={{ width: width * fitScale, height: height * fitScale, transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})` }}><img src={source} alt={result.metadata.filename} draggable={false} onLoad={(event) => setPreviewSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />{renderOverlay && annotated && <svg className="annotation-overlay" viewBox={`0 0 ${width} ${height}`} aria-label="天体标注图层"><defs><mask id={maskId} maskUnits="userSpaceOnUse" x={0} y={0} width={width} height={height}><rect width={width} height={height} fill="white" />{protectedCores.map((core, index) => <circle key={index} cx={core.x} cy={core.y} r={core.coreRadius} fill="black" />)}</mask></defs><g mask={`url(#${maskId})`}>{visibleObjects.map((object) => <Annotation key={object.id} object={object} width={width} height={height} selected={object.id === selected?.id} settings={settings} onSelect={onSelect} />)}</g></svg>}</div> : <div className="canvas-unavailable"><p>正在读取照片预览</p></div>}
      {progress && <div className="reanalyze-overlay" role="status"><strong>{progress.title}</strong><span>{progress.detail} · {progress.percent}%</span><div className="progress-bar"><i style={{ width: `${progress.percent}%` }} /></div></div>}
    </div>
    <footer className="canvas-status"><div className="status-metrics"><span>X: {cursor?.x ?? '—'}　Y: {cursor?.y ?? '—'}</span><span>{result.wcs.fieldOfView ? `视场 ${result.wcs.fieldOfView}` : '星图已解算'}</span>{result.wcs.matchedStars !== undefined && <span>匹配 {result.wcs.matchedStars} 星</span>}</div><div className="canvas-scale"><span>{isReducedPreview ? '预览' : '比例'} {actualPercent}%</span><span title={isReducedPreview ? `预览 ${previewSize?.width} × ${previewSize?.height}；导出原尺寸` : undefined}>{isReducedPreview ? '输出 ' : ''}{width} × {height}</span><span>本地处理</span></div></footer>
  </section>
}
