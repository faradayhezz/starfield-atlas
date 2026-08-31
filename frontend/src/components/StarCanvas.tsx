import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent,
} from 'react'
import { selectOverlayObjects } from '../overlay'
import type { AnalysisProgress, AnalysisResult, AnalysisSettings, DetectedObject } from '../types'
import { CheckIcon, FitIcon, ImageAddIcon, ZoomInIcon, ZoomOutIcon } from './Icons'

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

const coordinate = (value: number | undefined, extent: number) => {
  if (value === undefined) return undefined
  return Math.abs(value) <= 1 ? value * extent : value
}

function Annotation({ object, width, height, selected, settings, onSelect }: {
  object: DetectedObject
  width: number
  height: number
  selected: boolean
  settings: AnalysisSettings
  onSelect: (object: DetectedObject) => void
}) {
  const color = object.category === 'deepSky'
    ? settings.deepSkyColor
    : object.category === 'brightStars'
      ? settings.brightStarColor
      : settings.constellationColor
  const highContrast = settings.highContrast
  const x = coordinate(object.x, width)
  const y = coordinate(object.y, height)
  const radiusValue = object.radius && object.radius <= 1 ? object.radius * Math.min(width, height) : object.radius
  const radius = radiusValue ?? (object.category === 'deepSky' ? width / 95 : width / 330)
  // Keep the on-screen SVG and the full-resolution Canvas export visually
  // equivalent when they are viewed at the same scale.
  const fontSize = Math.max(24, width / 84)
  // `vectorEffect="non-scaling-stroke"` keeps these values in screen pixels.
  // Fixed widths avoid huge constellation bands on high-resolution photos.
  const lineWidth = 1.8
  const contrastWidth = highContrast ? 4.8 : 3.2
  const labelX = coordinate(object.labelX, width) ?? (x !== undefined ? x + radius + fontSize * .35 : undefined)
  const labelY = coordinate(object.labelY, height) ?? y
  return (
    <g
      className={`annotation annotation--${object.category} ${selected ? 'is-selected' : ''}`}
      style={{
        color,
        opacity: object.category === 'constellations' ? Math.max(.2, Math.min(1, settings.constellations.value / 100)) : 1,
      }}
      onClick={(event) => { event.stopPropagation(); onSelect(object) }}
    >
      <title>{object.label}</title>
      {object.lines?.map((line, lineIndex) => (
        <g key={`${object.id}-line-${lineIndex}`}>
          {highContrast && (
            <polyline
              points={line.map((point) => `${coordinate(point.x, width) ?? 0},${coordinate(point.y, height) ?? 0}`).join(' ')}
              fill="none"
              stroke="#020405"
              strokeOpacity=".92"
              strokeWidth={contrastWidth}
              vectorEffect="non-scaling-stroke"
            />
          )}
          <polyline
            points={line.map((point) => `${coordinate(point.x, width) ?? 0},${coordinate(point.y, height) ?? 0}`).join(' ')}
            fill="none"
            stroke="currentColor"
            strokeWidth={lineWidth}
            vectorEffect="non-scaling-stroke"
          />
        </g>
      ))}
      {x !== undefined && y !== undefined && (
        <>
          {highContrast && <circle cx={x} cy={y} r={radius} fill="none" stroke="#020405" strokeOpacity=".95" strokeWidth={selected ? 7 : 5.2} vectorEffect="non-scaling-stroke" />}
          <circle cx={x} cy={y} r={radius} fill="none" stroke="currentColor" strokeWidth={selected ? 3.5 : 2.2} vectorEffect="non-scaling-stroke" />
          {object.category === 'brightStars' && (
            <>
              {highContrast && <circle cx={x} cy={y} r={Math.max(4, width / 800)} fill="#020405" />}
              <circle cx={x} cy={y} r={Math.max(2.5, width / 900)} fill="currentColor" />
            </>
          )}
          {labelX !== undefined && labelY !== undefined && (
            <text
              x={labelX}
              y={labelY}
              dominantBaseline="middle"
              fontSize={fontSize}
              fontWeight={settings.fontWeight}
              fill="currentColor"
              stroke={highContrast ? '#020405' : 'rgba(7, 10, 12, .76)'}
              strokeWidth={Math.max(4, fontSize / (highContrast ? 4.5 : 8))}
              strokeLinejoin="round"
              paintOrder="stroke"
            >
              {object.label}
            </text>
          )}
        </>
      )}
    </g>
  )
}

function CompactDrop({ onBrowse, onFile }: Pick<StarCanvasProps, 'onBrowse' | 'onFile'>) {
  const [dragging, setDragging] = useState(false)
  const drop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files.item(0)
    if (file) onFile(file)
  }
  return (
    <button
      className={`compact-drop ${dragging ? 'is-dragging' : ''}`}
      type="button"
      onClick={onBrowse}
      onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={drop}
    >
      <ImageAddIcon />
      <strong>替换照片</strong>
      <span>点击选择或拖入新照片</span>
    </button>
  )
}

function CanvasStatus({ result, zoom, onZoom, onReset }: {
  result: AnalysisResult
  zoom: number
  onZoom: (zoom: number) => void
  onReset: () => void
}) {
  const { wcs } = result
  const matched = wcs.matchedStars !== undefined
    ? `${wcs.matchedStars.toLocaleString()}${wcs.catalogStars ? ` / ${wcs.catalogStars.toLocaleString()}` : ''}${wcs.matchRate !== undefined ? ` (${wcs.matchRate.toFixed(1)}%)` : ''}`
    : '星图已解算'
  return (
    <footer className="canvas-status">
      <div className="status-metrics">
        <span className="status-success"><CheckIcon />识别完成</span>
        <span>匹配星数：{matched}</span>
        {wcs.fieldOfView && <span>视场：{wcs.fieldOfView}</span>}
        {wcs.centerCoordinates && <span>定位：{wcs.centerCoordinates}</span>}
      </div>
      <div className="zoom-controls" aria-label="画布缩放">
        <button type="button" onClick={() => onZoom(Math.max(50, zoom - 25))} aria-label="缩小星图"><ZoomOutIcon /></button>
        <output aria-live="polite">{zoom}%</output>
        <button type="button" onClick={() => onZoom(Math.min(400, zoom + 25))} aria-label="放大星图"><ZoomInIcon /></button>
        <button className="fit-button" type="button" onClick={onReset}><FitIcon />适应窗口</button>
      </div>
    </footer>
  )
}

export function StarCanvas({ result, settings, source, renderOverlay, selected, progress, onBrowse, onFile, onSelect }: StarCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ pointerId: number; x: number; y: number; panX: number; panY: number } | undefined>(undefined)
  const [zoom, setZoom] = useState(100)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [panning, setPanning] = useState(false)
  const width = result.metadata.width ?? 1920
  const height = result.metadata.height ?? 1280
  const visibleObjects = useMemo(
    () => selectOverlayObjects(result.objects, settings),
    [result.objects, settings],
  )

  useEffect(() => {
    if (!selected || selected.x === undefined || selected.y === undefined) return
    const canvas = canvasRef.current
    if (!canvas) return
    const x = coordinate(selected.x, width) ?? width / 2
    const y = coordinate(selected.y, height) ?? height / 2
    const rect = canvas.getBoundingClientRect()
    const fitScale = Math.min(rect.width / width, rect.height / height)
    const nextZoom = Math.max(zoom, 160)
    const scale = nextZoom / 100
    setZoom(nextZoom)
    setPan({
      x: -(x - width / 2) * fitScale * scale,
      y: -(y - height / 2) * fitScale * scale,
    })
  }, [selected, width, height])

  const changeZoom = (next: number) => {
    const clamped = Math.max(50, Math.min(400, Math.round(next)))
    setPan((current) => {
      if (clamped === 100) return { x: 0, y: 0 }
      const ratio = clamped / zoom
      return { x: current.x * ratio, y: current.y * ratio }
    })
    setZoom(clamped)
  }

  const resetView = () => {
    setZoom(100)
    setPan({ x: 0, y: 0 })
  }

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    if (!source || progress) return
    event.preventDefault()
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const currentScale = zoom / 100
    const nextZoom = Math.max(50, Math.min(400, zoom + (event.deltaY < 0 ? 20 : -20)))
    if (nextZoom === zoom) return
    const nextScale = nextZoom / 100
    const focalX = event.clientX - rect.left - rect.width / 2
    const focalY = event.clientY - rect.top - rect.height / 2
    const worldX = (focalX - pan.x) / currentScale
    const worldY = (focalY - pan.y) / currentScale
    setPan({
      x: focalX - worldX * nextScale,
      y: focalY - worldY * nextScale,
    })
    setZoom(nextZoom)
  }

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!source || progress || event.button !== 0) return
    const target = event.target as Element
    if (target.closest('button, .annotation')) return
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y }
    setPanning(true)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    setPan({ x: drag.panX + event.clientX - drag.x, y: drag.panY + event.clientY - drag.y })
  }

  const finishPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    dragRef.current = undefined
    setPanning(false)
  }

  useEffect(resetView, [result.jobId, source])

  return (
    <section className="canvas-column" aria-label="星图标注预览">
      <div
        ref={canvasRef}
        className={`star-canvas ${source ? 'is-pannable' : ''} ${panning ? 'is-panning' : ''}`}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPan}
        onPointerCancel={finishPan}
        aria-describedby="canvas-help"
      >
        <p id="canvas-help" className="visually-hidden">滚动鼠标滚轮缩放，按住并拖动可平移星图；选择天体结果可将其定位到画面中央。</p>
        {source ? (
          <div className="image-stage" style={{ transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom / 100})` }}>
            <img src={source} alt={`${result.metadata.filename} 的星空识别结果`} draggable={false} />
            {renderOverlay && (
              <svg className="annotation-overlay" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" aria-label="天体标注图层">
                {visibleObjects.map((object) => <Annotation key={object.id} object={object} width={width} height={height} selected={selected?.id === object.id} settings={settings} onSelect={onSelect} />)}
              </svg>
            )}
          </div>
        ) : (
          <div className="canvas-unavailable"><ImageAddIcon /><p>浏览器无法直接预览此格式</p><span>识别完成后将显示后端生成的标注图</span></div>
        )}
        <CompactDrop onBrowse={onBrowse} onFile={onFile} />
        {progress && (
          <div className="reanalyze-overlay" role="status" aria-live="polite">
            <div className="solver-orbit solver-orbit--small" aria-hidden="true"><span /><span /><span /></div>
            <strong>{progress.title}</strong>
            <span>{progress.detail} · {progress.percent}%</span>
            <div className="progress-bar"><i style={{ width: `${progress.percent}%` }} /></div>
          </div>
        )}
      </div>
      <CanvasStatus result={result} zoom={zoom} onZoom={changeZoom} onReset={resetView} />
    </section>
  )
}
