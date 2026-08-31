import { useState, type DragEvent } from 'react'
import {
  firstSupportedFileFromTransfer,
  INCOMING_FILE_READ_ERROR,
  INCOMING_FILE_UNSUPPORTED_ERROR,
  transferCarriesFiles,
} from '../incomingFile'
import type { AnalysisProgress, AnalysisSettings, LayerKey } from '../types'
import { AlertIcon, ChevronRightIcon, ImageAddIcon, LockIcon } from './Icons'
import { Toggle } from './Toggle'

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

const STEP_LABELS = ['读取 EXIF', '星图解算', '目录匹配', '生成标注']

function Stepper({ current = 0, complete = false }: { current?: number; complete?: boolean }) {
  return (
    <ol className="analysis-stepper" aria-label="识别步骤">
      {STEP_LABELS.map((label, index) => {
        const active = complete || index <= current
        return (
          <li key={label} className={active ? 'is-active' : ''} aria-current={!complete && index === current ? 'step' : undefined}>
            <span className="step-number">{index + 1}</span>
            <span className="step-label">{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

const formatElapsed = (seconds = 0) => {
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return `${minutes.toString().padStart(2, '0')}:${remainder.toString().padStart(2, '0')}`
}

const formatBytes = (bytes: number) => bytes >= 1024 * 1024
  ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  : `${Math.max(0, Math.round(bytes / 1024))} KB`

function ProgressContent({ progress, filename, onCancel }: { progress: AnalysisProgress; filename?: string; onCancel: () => void }) {
  const hasTransferProgress = progress.receivedBytes !== undefined && progress.totalBytes !== undefined
  return (
    <div className="progress-content" role="status" aria-live="polite">
      <div className="solver-orbit" aria-hidden="true"><span /><span /><span /></div>
      <p className="progress-filename">{filename}</p>
      <h1>{progress.title}</h1>
      <p>{progress.detail}</p>
      <div className="progress-bar" aria-label={`识别进度 ${progress.percent}%`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress.percent}>
        <span style={{ width: `${progress.percent}%` }} />
      </div>
      <div className="progress-status-row">
        <span className="progress-percent">真实进度 {progress.percent}%</span>
        <span>已用时 {formatElapsed(progress.elapsedSeconds)}</span>
      </div>
      {hasTransferProgress && (
        <span className="progress-transfer">已接收 {formatBytes(progress.receivedBytes ?? 0)} / {formatBytes(progress.totalBytes ?? 0)}</span>
      )}
      <button className="cancel-analysis-button" type="button" onClick={onCancel}>取消识别</button>
    </div>
  )
}

function UploadDropZone({ progress, error, filename, onBrowse, onFile, onRetry, onCancel, onIncomingError }: Pick<UploadScreenProps, 'progress' | 'error' | 'filename' | 'onBrowse' | 'onFile' | 'onRetry' | 'onCancel' | 'onIncomingError'>) {
  const [dragging, setDragging] = useState(false)
  const canSelectFile = !progress && !error
  const onDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    if (!canSelectFile) return
    event.stopPropagation()
    try {
      const file = await firstSupportedFileFromTransfer(event.dataTransfer)
      if (file) onFile(file)
      else onIncomingError(INCOMING_FILE_UNSUPPORTED_ERROR)
    } catch (caught) {
      onIncomingError(caught instanceof Error ? caught.message : INCOMING_FILE_READ_ERROR)
    }
  }
  return (
    <div
      className={`upload-drop-zone ${dragging ? 'is-dragging' : ''} ${progress ? 'is-analyzing' : ''}`}
      onDragEnter={(event) => {
        event.preventDefault()
        if (transferCarriesFiles(event.dataTransfer)) setDragging(true)
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => { if (event.currentTarget === event.target) setDragging(false) }}
      onDrop={onDrop}
      onClick={() => { if (canSelectFile) onBrowse() }}
      onKeyDown={(event) => {
        if (!canSelectFile || event.target !== event.currentTarget) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onBrowse()
        }
      }}
      role={canSelectFile ? 'button' : 'group'}
      tabIndex={canSelectFile ? 0 : undefined}
      aria-label="拖拽星空照片到这里，或按回车选择文件"
    >
      {progress ? (
        <ProgressContent progress={progress} filename={filename} onCancel={onCancel} />
      ) : error ? (
        <div className="upload-error" role="alert">
          <AlertIcon />
          <h1>这次没有识别成功</h1>
          <p>{error}</p>
          <div className="error-actions">
            <button className="primary-button" type="button" onClick={(event) => { event.stopPropagation(); onRetry() }}>重新尝试</button>
            <button className="text-button" type="button" onClick={(event) => { event.stopPropagation(); onBrowse() }}>选择其他照片</button>
          </div>
        </div>
      ) : (
        <div className="upload-prompt">
          <ImageAddIcon className="upload-illustration" />
          <h1>上传一张星空照片</h1>
          <p>从资源管理器或微信拖入照片，也可点击选择</p>
          <span>支持 JPG、PNG、TIFF，单张最大 200 MB</span>
          <span>微信虚拟图片可复制后按 Ctrl+V</span>
          <span className="primary-button upload-prompt-action" aria-hidden="true">选择照片</span>
          <small><LockIcon />照片仅在本机处理</small>
        </div>
      )}
    </div>
  )
}

const settingKey = (key: LayerKey): keyof AnalysisSettings => key

function UploadSidebar({ settings, onSettingsChange }: Pick<UploadScreenProps, 'settings' | 'onSettingsChange'>) {
  const setLayer = (key: LayerKey, enabled: boolean) => {
    onSettingsChange({ ...settings, [settingKey(key)]: { ...settings[key], enabled } })
  }

  return (
    <aside className="upload-sidebar" aria-label="照片要求和识别设置">
      <section className="sidebar-section layer-picks">
        <h2>将识别并标注</h2>
        <Toggle checked={settings.deepSky.enabled} onChange={(checked) => setLayer('deepSky', checked)} label="深空天体" description="星系、星云、星团等" color="green" />
        <Toggle checked={settings.brightStars.enabled} onChange={(checked) => setLayer('brightStars', checked)} label="亮星" description="亮度较高的恒星" color="gold" />
        <Toggle checked={settings.constellations.enabled} onChange={(checked) => setLayer('constellations', checked)} label="星座连线" description="传统星座连线" color="purple" />
      </section>
      <section className="sidebar-section requirement-section">
        <h2>照片要求</h2>
        <dl className="requirement-list">
          <div><dt>文件格式</dt><dd>JPG、PNG、TIFF</dd></div>
          <div><dt>位深要求</dt><dd>8 / 16 / 32 bit</dd></div>
          <div><dt>颜色模式</dt><dd>RGB 或 灰度</dd></div>
          <div><dt>最大文件大小</dt><dd>200 MB</dd></div>
          <div><dt>推荐分辨率</dt><dd>≥ 1920 × 1280</dd></div>
          <div><dt>焦距信息</dt><dd>建议包含 EXIF 焦距</dd></div>
          <div><dt>拍摄时间</dt><dd>建议包含拍摄时间</dd></div>
        </dl>
      </section>
      <details className="advanced-settings">
        <summary><span>高级设置</span><ChevronRightIcon /></summary>
        <div className="advanced-settings__body">
          <label>
            <span>目录深度</span>
            <select value={settings.catalogDepth} onChange={(event) => onSettingsChange({ ...settings, catalogDepth: event.target.value as AnalysisSettings['catalogDepth'] })}>
              <option value="bright">仅明亮天体</option>
              <option value="balanced">平衡</option>
              <option value="deep">深度目录</option>
            </select>
          </label>
          <label>
            <span>标签密度</span>
            <select value={settings.labelDensity} onChange={(event) => onSettingsChange({ ...settings, labelDensity: event.target.value as AnalysisSettings['labelDensity'] })}>
              <option value="sparse">稀疏</option>
              <option value="balanced">自动</option>
              <option value="dense">密集</option>
            </select>
          </label>
        </div>
      </details>
      <div className="catalog-ready" role="status" title="OpenNGC v20260501 · Hipparcos hip_main · Celestial Data / d3-celestial J2000 · NASA Image and Video Library">
        <i aria-hidden="true" />
        <span><strong>离线星表与天体图文已就绪</strong><small>OpenNGC · Hipparcos · IAU 星座线 · NASA</small></span>
      </div>
    </aside>
  )
}

export function UploadScreen(props: UploadScreenProps) {
  return (
    <main className="upload-layout">
      <section className="upload-workspace" aria-label="上传照片">
        <UploadDropZone {...props} />
        <Stepper current={props.progress?.stage ?? 0} />
      </section>
      <UploadSidebar settings={props.settings} onSettingsChange={props.onSettingsChange} />
    </main>
  )
}
