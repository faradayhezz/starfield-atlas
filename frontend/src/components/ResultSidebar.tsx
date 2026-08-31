import { useEffect, useMemo, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { selectOverlayObjects } from '../overlay'
import {
  DEFAULT_SETTINGS,
  LAYER_LABELS,
  type AnalysisResult,
  type AnalysisSettings,
  type AnnotationFontWeight,
  type DetectedObject,
  type LayerKey,
} from '../types'
import { ChevronRightIcon, CrosshairIcon, LocationIcon, MapIcon } from './Icons'
import { Toggle } from './Toggle'

interface ResultSidebarProps {
  result: AnalysisResult
  settings: AnalysisSettings
  selectedId?: string
  imageSource?: string
  settingsDirty?: boolean
  onSettingsChange: (settings: AnalysisSettings) => void
  onApplySettings: () => void
  onSelect: (object: DetectedObject) => void
  onOpenSkyMap: () => void
}

type InspectorTab = 'results' | 'layers' | 'info'

const layerTabs: LayerKey[] = ['deepSky', 'brightStars', 'constellations']
const inspectorTabs: { id: InspectorTab; label: string }[] = [
  { id: 'results', label: '识别结果' },
  { id: 'layers', label: '图层与样式' },
  { id: 'info', label: '图像信息' },
]

const COLOR_PRESETS: Record<LayerKey, { color: string; label: string }[]> = {
  deepSky: [
    { color: '#18DF69', label: '荧光绿' },
    { color: '#39E6FF', label: '高亮青' },
    { color: '#FF6B9C', label: '亮粉色' },
    { color: '#FF9D3D', label: '橙色' },
    { color: '#FFFFFF', label: '白色' },
  ],
  brightStars: [
    { color: '#F4CE3A', label: '星光黄' },
    { color: '#FFFFFF', label: '白色' },
    { color: '#55DFFF', label: '天蓝色' },
    { color: '#FF795E', label: '珊瑚红' },
    { color: '#B9F45A', label: '黄绿色' },
  ],
  constellations: [
    { color: '#B86AE6', label: '星云紫' },
    { color: '#5B9DFF', label: '亮蓝色' },
    { color: '#FF69C7', label: '品红色' },
    { color: '#FF9D3D', label: '橙色' },
    { color: '#FFFFFF', label: '白色' },
  ],
}

const FONT_WEIGHTS: { value: AnnotationFontWeight; label: string }[] = [
  { value: 500, label: '标准' },
  { value: 650, label: '加粗' },
  { value: 800, label: '特粗' },
]

const COLOR_SETTING_KEYS: Record<LayerKey, 'deepSkyColor' | 'brightStarColor' | 'constellationColor'> = {
  deepSky: 'deepSkyColor',
  brightStars: 'brightStarColor',
  constellations: 'constellationColor',
}

const compactDate = (value?: string) => {
  if (!value) return '刚刚'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(date).replaceAll('/', '-')
}

function SolveSummary({ result, onOpenSkyMap }: { result: AnalysisResult; onOpenSkyMap: () => void }) {
  const { metadata, wcs } = result
  const matched = wcs.matchedStars !== undefined
    ? `${wcs.matchedStars}${wcs.catalogStars ? ` / ${wcs.catalogStars}` : ''}`
    : '已解算'
  const warningCount = result.warnings?.length ?? 0
  return (
    <section className="solve-summary" aria-label="星图解算摘要">
      <div className="solve-summary__head">
        <div>
          <strong title={metadata.filename}>{metadata.filename}</strong>
          <span>{metadata.shootingParams ?? `${metadata.width ?? '—'} × ${metadata.height ?? '—'}`}</span>
        </div>
        <span className={warningCount ? 'solve-state solve-state--warning' : 'solve-state'}>
          <i aria-hidden="true" />{warningCount ? `${warningCount} 条提示` : '识别完成'}
        </span>
      </div>
      <dl className="solve-summary__metrics">
        <div><dt>匹配星数</dt><dd>{matched}</dd></div>
        <div><dt>视场</dt><dd>{wcs.fieldOfView ?? '—'}</dd></div>
        <div><dt>中心坐标</dt><dd title={wcs.centerCoordinates}>{wcs.centerCoordinates ?? '—'}</dd></div>
      </dl>
      <button className="open-sky-map-button" type="button" onClick={onOpenSkyMap} disabled={!wcs.frameBoundary?.length}>
        <MapIcon />
        <span><strong>在第一人称天空中定位</strong><small>DSS2 + Legacy + 2MASS · 显示照片真实视场</small></span>
        <ChevronRightIcon className="open-sky-map-button__arrow" />
      </button>
      {warningCount > 0 && <p className="solve-warning" title={result.warnings?.join('\n')}>{result.warnings?.[0]}</p>}
    </section>
  )
}

function InfoView({ result }: { result: AnalysisResult }) {
  const { metadata, wcs } = result
  const coordinate = metadata.latitude !== undefined && metadata.longitude !== undefined
    ? `${metadata.latitude.toFixed(4)}°, ${metadata.longitude.toFixed(4)}°`
    : undefined
  return (
    <section className="info-view">
      <div className="inspector-section-heading">
        <div><h2>照片与解算信息</h2><p>从 EXIF 和离线星图解算中读取</p></div>
      </div>
      <dl className="image-info-list">
        <div><dt>文件名</dt><dd title={metadata.filename}>{metadata.filename}</dd></div>
        {metadata.camera && <div><dt>相机</dt><dd>{metadata.camera}</dd></div>}
        {metadata.lens && <div><dt>镜头</dt><dd>{metadata.lens}</dd></div>}
        <div><dt>拍摄参数</dt><dd>{metadata.shootingParams ?? '未写入 EXIF'}</dd></div>
        <div><dt>图像尺寸</dt><dd>{metadata.width && metadata.height ? `${metadata.width} × ${metadata.height}` : '读取中'}</dd></div>
        {metadata.capturedAt && <div><dt>拍摄时间</dt><dd>{compactDate(metadata.capturedAt)}</dd></div>}
        {coordinate && <div><dt>拍摄坐标</dt><dd className="coordinate-value"><LocationIcon />{coordinate}</dd></div>}
        <div><dt>中心坐标</dt><dd>{wcs.centerCoordinates ?? '未提供'}</dd></div>
        <div><dt>像素比例</dt><dd>{wcs.pixelScale ?? '未提供'}</dd></div>
        <div><dt>画面旋转</dt><dd>{wcs.rotation ?? '未提供'}</dd></div>
        <div><dt>解算误差</dt><dd>{wcs.rmsError ?? '未提供'}</dd></div>
        <div><dt>识别状态</dt><dd className="success-value"><i />识别完成</dd></div>
        <div><dt>识别时间</dt><dd>{compactDate(metadata.analyzedAt)}</dd></div>
      </dl>
    </section>
  )
}

function SettingSlider({ label, layer, settings, onSettingsChange }: {
  label: string
  layer: LayerKey
  settings: AnalysisSettings
  onSettingsChange: (settings: AnalysisSettings) => void
}) {
  const setting = settings[layer]
  const color = layer === 'deepSky' ? 'green' : layer === 'brightStars' ? 'gold' : 'purple'
  const isInstant = layer === 'constellations'
  return (
    <div className={`setting-slider setting-slider--${color}`}>
      <Toggle checked={setting.enabled} onChange={(enabled) => onSettingsChange({ ...settings, [layer]: { ...setting, enabled } })} label={label} color={color} />
      <label className="range-control">
        <span>{isInstant ? '连线强度' : '识别阈值'}</span>
        <input type="range" min="0" max="100" step="1" value={setting.value} style={{ '--range-percent': `${setting.value}%` } as CSSProperties} disabled={!setting.enabled} onChange={(event) => onSettingsChange({ ...settings, [layer]: { ...setting, value: Number(event.target.value) } })} aria-label={`${label}${isInstant ? '连线强度' : '识别阈值'}`} />
        <output>{setting.value}%</output>
      </label>
    </div>
  )
}

function LayerColorControl({ layer, settings, onSettingsChange }: {
  layer: LayerKey
  settings: AnalysisSettings
  onSettingsChange: (settings: AnalysisSettings) => void
}) {
  const colorKey = COLOR_SETTING_KEYS[layer]
  const current = settings[colorKey].toUpperCase()
  const setColor = (color: string) => onSettingsChange({ ...settings, [colorKey]: color.toUpperCase() })
  return (
    <div className="annotation-color-row">
      <span>{LAYER_LABELS[layer]}</span>
      <div className="color-swatches" role="group" aria-label={`${LAYER_LABELS[layer]}标注颜色`}>
        {COLOR_PRESETS[layer].map((preset) => <button key={preset.color} className={current === preset.color ? 'is-selected' : ''} type="button" style={{ '--swatch-color': preset.color } as CSSProperties} aria-label={`${LAYER_LABELS[layer]}：${preset.label}`} aria-pressed={current === preset.color} title={preset.label} onClick={() => setColor(preset.color)} />)}
        <label className="custom-color" title={`自定义${LAYER_LABELS[layer]}颜色`}>
          <input type="color" value={settings[colorKey]} aria-label={`自定义${LAYER_LABELS[layer]}颜色`} onChange={(event) => setColor(event.target.value)} />
          <span>自定</span>
        </label>
      </div>
    </div>
  )
}

function StylePreview({ settings }: { settings: AnalysisSettings }) {
  const shadow = settings.highContrast ? '0 1px 0 #000, 1px 0 0 #000, -1px 0 0 #000, 0 -1px 0 #000' : undefined
  return (
    <div className="annotation-style-preview" aria-label="当前标注样式预览">
      <span style={{ color: settings.deepSkyColor, fontWeight: settings.fontWeight, textShadow: shadow }}>○ M31 仙女座星系</span>
      <span style={{ color: settings.brightStarColor, fontWeight: settings.fontWeight, textShadow: shadow }}>⊙ 壁宿二</span>
      <span style={{ color: settings.constellationColor, fontWeight: settings.fontWeight, textShadow: shadow }}>— 仙女座</span>
    </div>
  )
}

function LayersView({ settings, settingsDirty, onSettingsChange, onApplySettings }: Pick<ResultSidebarProps, 'settings' | 'settingsDirty' | 'onSettingsChange' | 'onApplySettings'>) {
  const restoreStyle = () => onSettingsChange({ ...settings, deepSkyColor: DEFAULT_SETTINGS.deepSkyColor, brightStarColor: DEFAULT_SETTINGS.brightStarColor, constellationColor: DEFAULT_SETTINGS.constellationColor, fontWeight: DEFAULT_SETTINGS.fontWeight, highContrast: DEFAULT_SETTINGS.highContrast })
  return (
    <section className="layers-view">
      <div className="inspector-section-heading"><div><h2>图层显示</h2><p>开关和星座强度会即时反映在照片上</p></div></div>
      <SettingSlider label="深空天体" layer="deepSky" settings={settings} onSettingsChange={onSettingsChange} />
      <SettingSlider label="亮星" layer="brightStars" settings={settings} onSettingsChange={onSettingsChange} />
      <SettingSlider label="星座" layer="constellations" settings={settings} onSettingsChange={onSettingsChange} />
      <div className="recognition-scope">
        <div className="inspector-section-heading inspector-section-heading--compact"><div><h2>重新识别参数</h2><p>阈值、目录深度和密度更改后需要应用</p></div></div>
        <div className="select-grid">
          <label><span>目录深度</span><select value={settings.catalogDepth} onChange={(event) => onSettingsChange({ ...settings, catalogDepth: event.target.value as AnalysisSettings['catalogDepth'] })}><option value="bright">仅明亮天体</option><option value="balanced">平衡</option><option value="deep">深度目录</option></select></label>
          <label><span>标签密度</span><select value={settings.labelDensity} onChange={(event) => onSettingsChange({ ...settings, labelDensity: event.target.value as AnalysisSettings['labelDensity'] })}><option value="sparse">稀疏</option><option value="balanced">自动</option><option value="dense">密集</option></select></label>
        </div>
        <button className="apply-settings-button" type="button" onClick={onApplySettings} disabled={!settingsDirty}>{settingsDirty ? '应用并重新识别' : '识别参数已应用'}</button>
      </div>
      <div className="annotation-style-section">
        <div className="inspector-section-heading inspector-section-heading--compact"><div><h2>标注样式</h2><p>颜色、粗细与对比度即时预览，也会用于下载图</p></div><button className="reset-style-button" type="button" onClick={restoreStyle}>恢复默认</button></div>
        <StylePreview settings={settings} />
        {layerTabs.map((layer) => <LayerColorControl key={layer} layer={layer} settings={settings} onSettingsChange={onSettingsChange} />)}
        <div className="font-weight-row"><span>字体粗细</span><div className="font-weight-picks" role="group" aria-label="标注字体粗细">{FONT_WEIGHTS.map((option) => <button key={option.value} className={settings.fontWeight === option.value ? 'is-selected' : ''} type="button" style={{ fontWeight: option.value }} aria-pressed={settings.fontWeight === option.value} onClick={() => onSettingsChange({ ...settings, fontWeight: option.value })}>{option.label}</button>)}</div></div>
        <div className="contrast-control"><Toggle checked={settings.highContrast} onChange={(highContrast) => onSettingsChange({ ...settings, highContrast })} label="高对比度" description="加强文字描边与线条暗边" /></div>
      </div>
    </section>
  )
}

const thumbnailSource = (source?: string) => {
  if (!source) return undefined
  if (/^(data:|blob:|https?:|\/)/.test(source)) return source
  return `data:image/png;base64,${source}`
}

function ObjectThumbnail({ object, imageSource, width, height }: { object: DetectedObject; imageSource?: string; width?: number; height?: number }) {
  const catalogThumbnail = thumbnailSource(object.thumbnail)
  const source = catalogThumbnail ?? imageSource
  const x = object.x !== undefined && width ? (Math.abs(object.x) <= 1 ? object.x * 100 : object.x / width * 100) : 50
  const y = object.y !== undefined && height ? (Math.abs(object.y) <= 1 ? object.y * 100 : object.y / height * 100) : 50
  return <span className={`object-thumbnail object-thumbnail--${object.category}`} style={source ? { backgroundImage: `url("${source.replaceAll('"', '%22')}")`, backgroundPosition: catalogThumbnail ? 'center' : `${x}% ${y}%`, backgroundSize: catalogThumbnail ? 'cover' : undefined } : undefined} aria-hidden="true" />
}

function ObjectCard({ object, selected, result, imageSource, onSelect }: { object: DetectedObject; selected: boolean; result: AnalysisResult; imageSource?: string; onSelect: (object: DetectedObject) => void }) {
  const details = [object.type, object.magnitude !== undefined ? `视等 ${object.magnitude}` : undefined, object.angularSize, object.mediaProvider === 'NASA' ? 'NASA 图文' : undefined].filter(Boolean)
  return (
    <button className={`object-card object-card--${object.category} ${selected ? 'is-selected' : ''}`} type="button" aria-pressed={selected} onClick={() => onSelect(object)}>
      <ObjectThumbnail object={object} imageSource={imageSource} width={result.metadata.width} height={result.metadata.height} />
      <span className="object-card__copy"><strong>{object.label}</strong><span>{details.length ? details.join(' · ') : object.description ?? '目录匹配天体'}</span>{object.ra && object.dec && <small>RA {object.ra} · Dec {object.dec}</small>}</span>
      <CrosshairIcon className="object-locate-icon" />
    </button>
  )
}

const safeNasaUrl = (value?: string) => {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && (url.hostname === 'nasa.gov' || url.hostname.endsWith('.nasa.gov')) ? url.href : undefined
  } catch {
    return undefined
  }
}

function ObjectDetail({ object }: { object: DetectedObject }) {
  const sourceUrl = safeNasaUrl(object.sourceUrl)
  const image = thumbnailSource(object.thumbnail)
  if (!object.description && !sourceUrl && !image) return null
  const classification = object.objectClassDetail ?? object.type
  return (
    <article className={`object-detail ${image ? 'has-image' : ''}`} aria-label={`${object.label} 天体资料`}>
      {image && <img src={image} alt={`${object.label} 的 NASA 天文观测图`} />}
      <div className="object-detail__body">
        <span className="object-detail__eyebrow"><i aria-hidden="true" />NASA 天体资料</span>
        <h3>{object.label}</h3>
        {object.titleEn && <p className="object-detail__english">{object.titleEn}</p>}
        {(classification || object.distance) && <p className="object-detail__facts">{[classification, object.distance].filter(Boolean).join(' · ')}</p>}
        {object.description && <p className="object-detail__description">{object.description}</p>}
      </div>
      <footer>
        <small title={object.imageCredit}>图像来源：{object.imageCredit ?? 'NASA'}</small>
        {sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">查看 NASA 原始资料 <span aria-hidden="true">↗</span></a>}
      </footer>
    </article>
  )
}

function ObjectsView({ result, settings, selectedId, imageSource, onSelect }: Pick<ResultSidebarProps, 'result' | 'settings' | 'selectedId' | 'imageSource' | 'onSelect'>) {
  const visibleObjects = useMemo(() => selectOverlayObjects(result.objects, settings), [result.objects, settings])
  const firstNonEmpty = layerTabs.find((tab) => visibleObjects.some((object) => object.category === tab)) ?? 'deepSky'
  const [activeTab, setActiveTab] = useState<LayerKey>(firstNonEmpty)
  const counts = useMemo(() => Object.fromEntries(layerTabs.map((tab) => [tab, tab === 'constellations' ? new Set(visibleObjects.filter((object) => object.category === tab).map((object) => object.constellation ?? object.label)).size : visibleObjects.filter((object) => object.category === tab).length])) as Record<LayerKey, number>, [visibleObjects])
  const objects = visibleObjects.filter((object) => object.category === activeTab)
  const selectedObject = visibleObjects.find((object) => object.id === selectedId)
  const selectedWithDetails = selectedObject && (selectedObject.description || selectedObject.sourceUrl || selectedObject.thumbnail) ? selectedObject : undefined
  useEffect(() => {
    if (selectedObject && selectedObject.category !== activeTab) setActiveTab(selectedObject.category)
  }, [activeTab, selectedObject])
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? layerTabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + layerTabs.length) % layerTabs.length
    setActiveTab(layerTabs[nextIndex])
    document.getElementById(`object-tab-${layerTabs[nextIndex]}`)?.focus()
  }
  return (
    <section className={`objects-panel objects-panel--inspector ${selectedWithDetails ? 'has-object-detail' : ''}`}>
      <div className="result-tabs" role="tablist" aria-label="识别结果分类">
        {layerTabs.map((tab, index) => <button key={tab} id={`object-tab-${tab}`} type="button" role="tab" tabIndex={activeTab === tab ? 0 : -1} aria-selected={activeTab === tab} aria-controls="object-list-panel" className={`${activeTab === tab ? 'is-active' : ''} result-tab--${tab}`} onClick={() => setActiveTab(tab)} onKeyDown={(event) => onTabKeyDown(event, index)}>{LAYER_LABELS[tab]} <span>({counts[tab]})</span></button>)}
      </div>
      {selectedWithDetails && <ObjectDetail object={selectedWithDetails} />}
      <div id="object-list-panel" className="object-list" role="tabpanel" aria-labelledby={`object-tab-${activeTab}`} tabIndex={0}>
        {objects.length ? objects.map((object) => <ObjectCard key={object.id} object={object} selected={selectedId === object.id} result={result} imageSource={imageSource} onSelect={onSelect} />) : <div className="empty-result"><CrosshairIcon /><p>当前图层没有可见结果</p><span>可开启图层或降低阈值后重新识别</span></div>}
      </div>
      <div className="result-legend" aria-label="标注图例">{layerTabs.map((layer) => <span key={layer}><i style={{ borderColor: settings[COLOR_SETTING_KEYS[layer]], color: settings[COLOR_SETTING_KEYS[layer]] }} />{LAYER_LABELS[layer]}</span>)}<small title="OpenNGC v20260501 · Hipparcos hip_main · Celestial Data / d3-celestial J2000 · NASA Image and Video Library">OpenNGC · Hipparcos · IAU · NASA</small></div>
    </section>
  )
}

export function ResultSidebar(props: ResultSidebarProps) {
  const [activeTab, setActiveTab] = useState<InspectorTab>('results')
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const nextIndex = event.key === 'Home' ? 0 : event.key === 'End' ? inspectorTabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + inspectorTabs.length) % inspectorTabs.length
    setActiveTab(inspectorTabs[nextIndex].id)
    document.getElementById(`inspector-tab-${inspectorTabs[nextIndex].id}`)?.focus()
  }
  return (
    <aside className="result-sidebar" aria-label="识别结果检查器">
      <SolveSummary result={props.result} onOpenSkyMap={props.onOpenSkyMap} />
      <div className="inspector-tabs" role="tablist" aria-label="结果检查器">
        {inspectorTabs.map((tab, index) => <button key={tab.id} id={`inspector-tab-${tab.id}`} type="button" role="tab" tabIndex={activeTab === tab.id ? 0 : -1} aria-selected={activeTab === tab.id} aria-controls="inspector-panel" className={activeTab === tab.id ? 'is-active' : ''} onClick={() => setActiveTab(tab.id)} onKeyDown={(event) => onTabKeyDown(event, index)}>{tab.label}</button>)}
      </div>
      <div id="inspector-panel" className="inspector-content" role="tabpanel" aria-labelledby={`inspector-tab-${activeTab}`} tabIndex={0}>
        {activeTab === 'results' && <ObjectsView result={props.result} settings={props.settings} selectedId={props.selectedId} imageSource={props.imageSource} onSelect={props.onSelect} />}
        {activeTab === 'layers' && <LayersView settings={props.settings} settingsDirty={props.settingsDirty} onSettingsChange={props.onSettingsChange} onApplySettings={props.onApplySettings} />}
        {activeTab === 'info' && <InfoView result={props.result} />}
      </div>
    </aside>
  )
}
