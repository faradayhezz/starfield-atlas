import type { AnalysisProgress, AnalysisSettings } from '../types'
import { AlertIcon, ImageAddIcon } from './Icons'
import { AnnotationSettings } from './ResultSidebar'

interface UploadScreenProps {
  settings: AnalysisSettings
  progress?: AnalysisProgress
  error?: string
  filename?: string
  onSettingsChange: (settings: AnalysisSettings) => void
  onBrowse: () => void
  onFile: (file: File) => void
  onRetry: () => void
  onCancel: () => void
  onIncomingError: (message: string) => void
}

const STEP_LABELS = ['读取照片', '星图解算', '目录匹配', '生成预览']
const elapsed = (seconds = 0) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`

function UploadDropZone({ progress, error, filename, onBrowse, onRetry, onCancel }: UploadScreenProps) {
  const selectable = !progress && !error
  return <div className="upload-drop-zone" onClick={() => { if (selectable) onBrowse() }} onKeyDown={(event) => { if (selectable && event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) { event.preventDefault(); onBrowse() } }} role={selectable ? 'button' : 'group'} tabIndex={selectable ? 0 : undefined} aria-label="打开星空照片或拖放到此处">
    {progress ? <div className="progress-content" role="status" aria-live="polite"><p className="progress-filename">{filename}</p><h1>{progress.title}</h1><p>{progress.detail}</p><div className="progress-bar" role="progressbar" aria-label="解析进度" aria-valuenow={progress.percent} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${progress.percent}%` }} /></div><div className="progress-status-row"><span>{progress.percent}%</span><span>{elapsed(progress.elapsedSeconds)}</span></div>{progress.receivedBytes !== undefined && progress.totalBytes !== undefined && <p>已接收 {(progress.receivedBytes / 1048576).toFixed(1)} / {(progress.totalBytes / 1048576).toFixed(1)} MB</p>}<button className="cancel-analysis-button" type="button" onClick={onCancel}>取消解析</button></div> : error ? <div className="upload-error" role="alert"><AlertIcon /><h1>解析未完成</h1><p>{error}</p><div className="error-actions"><button type="button" className="primary-button" onClick={onRetry} disabled={!filename}>重新尝试</button><button type="button" className="text-button" onClick={onBrowse}>打开其他照片</button></div></div> : <div className="upload-prompt"><ImageAddIcon className="upload-illustration" /><h1>打开星空照片</h1><p>将照片拖到此处，或点击打开</p><span>JPG · PNG · TIFF · 相机 RAW</span><span className="primary-button upload-prompt-action" aria-hidden="true">打开照片</span><small>支持微信拖放与 Ctrl+V 粘贴 · 单张最大 200 MB</small></div>}
  </div>
}

export function UploadScreen(props: UploadScreenProps) {
  return <main className="upload-layout"><section className="upload-workspace" aria-label="照片工作区"><div className="empty-document-tab" title={props.filename}>{props.filename ?? '未打开照片'}</div><UploadDropZone {...props} /><footer className="upload-status"><ol className="analysis-stepper" aria-label="解析步骤">{STEP_LABELS.map((label, index) => <li key={label} className={props.progress && index <= props.progress.stage ? 'is-active' : ''}><span className="step-number">{index + 1}</span><span className="step-label">{label}</span></li>)}</ol><span>本地处理</span></footer></section><aside className="upload-sidebar" aria-label="解析设置"><div className="inspector-tabs"><span className="static-inspector-tab">照片解析</span></div><div className="inspector-content"><AnnotationSettings settings={props.settings} onSettingsChange={props.onSettingsChange} /><div className="source-catalog-note">HYG + Tycho-2 恒星目录 · OpenNGC · Lynds 暗星云<br />支持拍摄参数与 EXIF 自动读取</div></div></aside></main>
}
