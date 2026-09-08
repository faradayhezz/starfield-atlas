import { useDeferredValue, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { DEFAULT_SETTINGS, LAYER_LABELS, type AnalysisResult, type AnalysisSettings, type DetectedObject, type LayerKey } from '../types'
import { ChevronRightIcon, CrosshairIcon, MapIcon } from './Icons'

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

const LAYERS: LayerKey[] = ['deepSky', 'brightStars', 'constellations']
const COLOR_KEYS = { deepSky: 'deepSkyColor', brightStars: 'brightStarColor', constellations: 'constellationColor' } as const
const COLOR_PRESETS = ['#69BE7A', '#D4B953', '#A391BF', '#69B5C1', '#D290A8', '#D5D7DA', '#18DF69']

function SettingRange({ label, value, min, max, step = 1, suffix = '', onChange }: { label: string; value: number; min: number; max: number; step?: number; suffix?: string; onChange: (value: number) => void }) {
  return <label className="workbench-field range-field"><span>{label}</span><input type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /><output>{Number(value.toFixed(2))}{suffix}</output></label>
}

export function AnnotationSettings({ settings, onSettingsChange, settingsDirty, onApplySettings, result }: {
  settings: AnalysisSettings
  onSettingsChange: (settings: AnalysisSettings) => void
  settingsDirty?: boolean
  onApplySettings?: () => void
  result?: AnalysisResult
}) {
  const update = <K extends keyof AnalysisSettings>(key: K, value: AnalysisSettings[K]) => onSettingsChange({ ...settings, [key]: value })
  return <section className="workbench-settings">
    <div className="inspector-heading"><h2>标注设置</h2><button type="button" className="quiet-button" onClick={() => onSettingsChange({ ...DEFAULT_SETTINGS, catalogDepth: settings.catalogDepth, starMagnitudeLimit: settings.starMagnitudeLimit })}>重置样式</button></div>
    <fieldset className="layer-checkboxes"><legend>图层</legend>{LAYERS.map((layer) => <label key={layer}><input type="checkbox" checked={settings[layer].enabled} onChange={(event) => update(layer, { ...settings[layer], enabled: event.target.checked })} /><span>{layer === 'constellations' ? '星座连线' : LAYER_LABELS[layer]}</span></label>)}</fieldset>
    <label className="workbench-field"><span>深空目录</span><select value={settings.catalogDepth} onChange={(event) => update('catalogDepth', event.target.value as AnalysisSettings['catalogDepth'])}><option value="bright">常用天体</option><option value="balanced">扩展目录</option><option value="deep">完整目录</option></select></label>
    <SettingRange label="恒星极限星等" value={settings.starMagnitudeLimit} min={3} max={16} step={.5} onChange={(value) => update('starMagnitudeLimit', value)} />
    {settingsDirty && onApplySettings && <button className="apply-settings-button" type="button" onClick={onApplySettings}>应用目录参数 · 重新解析</button>}
    <label className="workbench-field"><span>标签密度</span><select value={settings.labelDensity} onChange={(event) => update('labelDensity', event.target.value as AnalysisSettings['labelDensity'])}><option value="sparse">稀疏</option><option value="balanced">平衡</option><option value="dense">密集</option></select></label>
    <SettingRange label="标注强度" value={Math.round(settings.annotationOpacity * 100)} min={10} max={100} suffix="%" onChange={(value) => update('annotationOpacity', value / 100)} />
    {settings.constellations.enabled && <SettingRange label="星座连线强度" value={settings.constellations.value} min={10} max={100} suffix="%" onChange={(value) => update('constellations', { ...settings.constellations, value })} />}
    <SettingRange label="线宽" value={settings.annotationLineWidth} min={.5} max={3} step={.25} suffix=" px" onChange={(value) => update('annotationLineWidth', value)} />
    <SettingRange label="文字尺寸" value={settings.annotationFontSize} min={9} max={24} suffix=" px" onChange={(value) => update('annotationFontSize', value)} />
    <div className="workbench-field"><span>字体粗细</span><div className="segmented-control">{([{ value: 500, label: '常规' }, { value: 650, label: '中等' }, { value: 800, label: '加粗' }] as const).map((weight) => <button key={weight.value} type="button" aria-pressed={settings.fontWeight === weight.value} onClick={() => update('fontWeight', weight.value)}>{weight.label}</button>)}</div></div>
    <label className="workbench-field"><span>定位标记</span><select value={settings.markerStyle} onChange={(event) => update('markerStyle', event.target.value as AnalysisSettings['markerStyle'])}><option value="circle">空心圆 · 中心留空</option><option value="corners">四角框 · 中心留空</option></select></label>
    <div className="annotation-colors"><span>标注颜色</span><div>{LAYERS.map((layer) => <div className="workbench-color-row" key={layer}><label><input type="color" aria-label={`${LAYER_LABELS[layer]}颜色`} value={settings[COLOR_KEYS[layer]]} onChange={(event) => update(COLOR_KEYS[layer], event.target.value)} /><span>{LAYER_LABELS[layer]}</span></label><div className="compact-swatches">{COLOR_PRESETS.map((color) => <button key={color} type="button" title={color} aria-label={`${LAYER_LABELS[layer]} ${color}`} style={{ '--swatch-color': color } as CSSProperties} onClick={() => update(COLOR_KEYS[layer], color)} />)}</div></div>)}</div></div>
    <label className="workbench-checkbox"><input type="checkbox" checked={settings.highContrast} onChange={(event) => update('highContrast', event.target.checked)} /><span>高对比描边</span></label>
    <label className="workbench-checkbox"><input type="checkbox" checked={settings.includeCatalogOnly} onChange={(event) => update('includeCatalogOnly', event.target.checked)} /><span>显示更多目录位置</span></label>
    <p className="field-help">目录位置不等于照片中实际可见。暗星、暗星云可从天体目录逐个定位。</p>
    <div className="export-summary"><h2>导出</h2><div className="export-format">原格式 · 原始像素</div>{result?.export ? <><p>{result.export.format} · {result.export.bitDepth} bit · {result.export.width} × {result.export.height}</p><p>{result.export.note}</p></> : <p>JPG / PNG / TIFF 保留像素尺寸与格式；RAW 显影后输出 16 位 TIFF。</p>}<p>标注会改变文件内容与体积，原始文件保留。</p></div>
  </section>
}

function ObjectDetail({ object }: { object: DetectedObject }) {
  const sourceUrl = (() => { try { const url = new URL(object.sourceUrl ?? ''); return url.protocol === 'https:' && (url.hostname === 'nasa.gov' || url.hostname.endsWith('.nasa.gov')) ? url.href : undefined } catch { return undefined } })()
  return <article className="catalog-detail">
    {object.thumbnail && <img src={object.thumbnail} alt={`${object.label} 天体资料图`} />}
    <h3>{object.label}</h3>
    <dl className="image-info-list"><div><dt>类型</dt><dd>{object.objectClassDetail ?? object.type ?? '恒星'}</dd></div><div><dt>星等</dt><dd>{object.magnitude?.toFixed(2) ?? '—'}</dd></div>{object.angularSize && <div><dt>角直径</dt><dd>{object.angularSize}</dd></div>}<div><dt>赤经 RA</dt><dd>{object.raDeg?.toFixed(6) ?? object.ra ?? '—'}°</dd></div><div><dt>赤纬 Dec</dt><dd>{object.decDeg?.toFixed(6) ?? object.dec ?? '—'}°</dd></div><div><dt>定位依据</dt><dd>{object.pixelDetected ? '像素匹配' : '星表坐标投影'}</dd></div></dl>
    {object.description && <p>{object.description}</p>}{object.distance && <p>{object.distance}</p>}
    {object.imageCredit && <small>图像：{object.imageCredit}</small>}{sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">NASA 原始资料</a>}
  </article>
}

function ObjectsView({ result, selectedId, onSelect }: Pick<ResultSidebarProps, 'result' | 'selectedId' | 'onSelect'>) {
  const [category, setCategory] = useState<LayerKey>('deepSky')
  const [search, setSearch] = useState('')
  const [magnitude, setMagnitude] = useState('')
  const [page, setPage] = useState(0)
  const deferredSearch = useDeferredValue(search)
  const selected = result.objects.find((object) => object.id === selectedId)
  const PAGE_SIZE = 60
  const counts = useMemo(() => Object.fromEntries(LAYERS.map((layer) => [layer, result.objects.filter((object) => object.category === layer).length])) as Record<LayerKey, number>, [result.objects])
  const filtered = useMemo(() => {
    const terms = deferredSearch.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
    return result.objects.filter((object) => object.category === category && (magnitude === '' || object.magnitude === undefined || object.magnitude <= Number(magnitude)) && terms.every((term) => `${object.label} ${object.name} ${object.id} ${object.type ?? ''}`.toLocaleLowerCase().includes(term)))
  }, [result.objects, category, deferredSearch, magnitude])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, pages - 1)
  useEffect(() => setPage(0), [category, deferredSearch, magnitude, result.jobId])
  useEffect(() => { if (selected) setCategory(selected.category) }, [selectedId])
  return <section className="catalog-panel">
    <div className="catalog-filters"><label className="catalog-search"><span className="visually-hidden">搜索天体目录</span><input type="search" placeholder="名称、编号、类型…" value={search} onChange={(event) => setSearch(event.target.value)} /></label><label className="catalog-magnitude"><span>星等 ≤</span><input type="number" min={-2} max={24} step={.5} value={magnitude} placeholder="不限" aria-label="筛选最大星等" onChange={(event) => setMagnitude(event.target.value)} /></label></div>
    <div className="catalog-categories" aria-label="目录分类">{LAYERS.map((layer) => <button type="button" key={layer} aria-pressed={category === layer} onClick={() => setCategory(layer)}>{LAYER_LABELS[layer]} <small>{counts[layer].toLocaleString()}</small></button>)}</div>
    <p className="catalog-caption">视场内目录位置 · {filtered.length.toLocaleString()} 项</p>
    <div className="catalog-table-wrap"><table className="catalog-table"><thead><tr><th>名称 / 编号</th><th>类型</th><th>星等</th><th><span className="visually-hidden">定位</span></th></tr></thead><tbody>{filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).map((object) => <tr key={object.id} className={selectedId === object.id ? 'is-selected' : ''}><td><button type="button" title={object.label} onClick={() => onSelect(object)}>{object.label}</button></td><td title={object.type}>{object.type ?? '恒星'}</td><td>{object.magnitude?.toFixed(1) ?? '—'}</td><td><button className="locate-object" type="button" aria-label={`定位 ${object.label}`} onClick={() => onSelect(object)}><CrosshairIcon /></button></td></tr>)}</tbody></table>{!filtered.length && <p className="catalog-empty">没有符合条件的目录项</p>}</div>
    <div className="catalog-pagination"><button type="button" onClick={() => setPage(Math.max(0, currentPage - 1))} disabled={currentPage === 0}>上一页</button><span>{currentPage + 1} / {pages}</span><button type="button" onClick={() => setPage(Math.min(pages - 1, currentPage + 1))} disabled={currentPage >= pages - 1}>下一页</button></div>
    {selected && <ObjectDetail object={selected} />}
    <p className="catalog-provenance">HYG · OpenNGC · Lynds · NASA<br />坐标匹配不代表目标已在照片中检出。</p>
  </section>
}

function InfoView({ result }: { result: AnalysisResult }) {
  const { metadata, wcs } = result
  const fields: [string, string | number | undefined][] = [['文件名', metadata.filename], ['相机', metadata.camera], ['镜头', metadata.lens], ['拍摄参数', metadata.shootingParams], ['图像尺寸', `${metadata.width} × ${metadata.height}`], ['拍摄时间', metadata.capturedAt], ['中心坐标', wcs.centerCoordinates], ['视场', wcs.fieldOfView], ['匹配恒星', wcs.matchedStars], ['像素比例', wcs.pixelScale], ['旋转角', wcs.rotation], ['解算误差', wcs.rmsError]]
  return <section className="info-view"><div className="inspector-heading"><h2>照片与解算信息</h2></div><dl className="image-info-list">{fields.filter(([, value]) => value !== undefined).map(([label, value]) => <div key={label}><dt>{label}</dt><dd title={String(value)}>{value}</dd></div>)}</dl>{result.export && <div className="export-summary"><h2>原始输出</h2><p>{result.export.format} · {result.export.bitDepth} bit · {result.export.width} × {result.export.height}</p><p>{result.export.note}</p></div>}{result.originalDownloadUrl && <a className="original-download" href={result.originalDownloadUrl} download>下载未改动的原文件</a>}{result.warnings?.length ? <div className="analysis-warnings"><h2>解析提示</h2>{result.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div> : null}</section>
}

export function ResultSidebar(props: ResultSidebarProps) {
  const [tab, setTab] = useState<'catalog' | 'style' | 'info'>('style')
  useEffect(() => { if (props.selectedId) setTab('catalog') }, [props.selectedId])
  return <aside className="result-sidebar" aria-label="照片检查器"><div className="inspector-tabs" role="tablist" aria-label="检查器">{([{ id: 'catalog', label: '天体目录' }, { id: 'style', label: '标注' }, { id: 'info', label: '信息' }] as const).map((item) => <button id={`inspector-tab-${item.id}`} key={item.id} type="button" role="tab" aria-selected={tab === item.id} aria-controls="inspector-panel" onClick={() => setTab(item.id)}>{item.label}</button>)}</div><div id="inspector-panel" className="inspector-content" role="tabpanel" aria-labelledby={`inspector-tab-${tab}`}>{tab === 'catalog' && <ObjectsView {...props} />}{tab === 'style' && <AnnotationSettings {...props} />}{tab === 'info' && <InfoView result={props.result} />}</div><button className="open-sky-map-button" type="button" onClick={props.onOpenSkyMap} disabled={!props.result.wcs.frameBoundary?.length}><MapIcon /><span>在天球中定位照片视场</span><ChevronRightIcon /></button></aside>
}
