import { useEffect, useMemo, useRef, useState } from 'react'
import { analyzePhoto, cancelAnalysis, getAnalysisProgress, type AnalysisTaskProgressResponse } from './api'
import { createAnnotatedBlob, downloadBlob, exportResultJson, getImageDimensions, sourceToBlob } from './export'
import {
  firstSupportedFileFromTransfer,
  hasSupportedImageExtension,
  INCOMING_FILE_READ_ERROR,
  INCOMING_FILE_UNSUPPORTED_ERROR,
  normalizeIncomingFile,
  transferCarriesFiles,
} from './incomingFile'
import { selectOverlayObjects } from './overlay'
import { Header } from './components/Header'
import { CloseIcon } from './components/Icons'
import { ResultSidebar } from './components/ResultSidebar'
import { StarCanvas } from './components/StarCanvas'
import { SkyMapDialog } from './components/SkyMapDialog'
import { UploadScreen } from './components/UploadScreen'
import { DEFAULT_SETTINGS, type AnalysisProgress, type AnalysisResult, type AnalysisSettings, type DetectedObject } from './types'

const MAX_FILE_SIZE = 200 * 1024 * 1024
const PROGRESS_POLL_MS = 400
const ANALYSIS_TIMEOUT_MS = 5 * 60 * 1000
const DIMENSION_TIMEOUT_MS = 5000

const requestId = (): string => {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID().replaceAll('-', '').toLowerCase()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
}

const stageIndex = (stage: string): number => {
  const normalized = stage.toLowerCase()
  if (normalized.includes('solv')) return 1
  if (normalized.includes('catalog') || normalized.includes('match')) return 2
  if (normalized.includes('preview') || normalized.includes('annotat') || normalized.includes('full') || normalized.includes('final') || normalized.includes('complete')) return 3
  return 0
}

const stageTitle = (stage: string): string => {
  const normalized = stage.toLowerCase()
  if (normalized.includes('receiv') || normalized.includes('upload')) return '正在接收照片'
  if (normalized.includes('valid') || normalized.includes('metadata') || normalized.includes('exif')) return '正在校验照片信息'
  if (normalized.includes('solv')) return '正在解算星图'
  if (normalized.includes('catalog') || normalized.includes('match')) return '正在匹配天体目录'
  if (normalized.includes('preview')) return '正在生成预览标注'
  if (normalized.includes('full') || normalized.includes('annotat')) return '正在生成高清标注'
  if (normalized.includes('final') || normalized.includes('complete')) return '正在整理识别结果'
  return '正在准备识别'
}

const progressFromServer = (latest: AnalysisTaskProgressResponse, elapsedSeconds: number): AnalysisProgress => ({
  stage: stageIndex(latest.stage),
  percent: Math.round(latest.percent),
  title: stageTitle(latest.stage),
  detail: latest.message,
  stageKey: latest.stage,
  elapsedSeconds,
  receivedBytes: latest.receivedBytes,
  totalBytes: latest.totalBytes,
})

const initialProgress = (): AnalysisProgress => ({
  stage: 0,
  percent: 0,
  title: '正在建立本地任务',
  detail: '准备接收照片，请稍候',
  stageKey: 'preparing',
  elapsedSeconds: 0,
})

function validatePhoto(file: File): string | undefined {
  if (!hasSupportedImageExtension(file.name)) return '请选择 JPG、PNG 或 TIFF 格式的星空照片。'
  if (file.size > MAX_FILE_SIZE) return '照片超过 200 MB，请先压缩或选择较小的文件。'
  if (file.size === 0) return '这个文件没有可读取的图像数据。'
  return undefined
}

const getImageDimensionsBounded = async (source: string): Promise<{ width?: number; height?: number }> => {
  let timer: number | undefined
  try {
    return await Promise.race([
      getImageDimensions(source).catch(() => ({ width: undefined, height: undefined })),
      new Promise<{ width?: number; height?: number }>((resolve) => {
        timer = window.setTimeout(() => resolve({ width: undefined, height: undefined }), DIMENSION_TIMEOUT_MS)
      }),
    ])
  } finally {
    if (timer !== undefined) window.clearTimeout(timer)
  }
}

function App() {
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | undefined>(undefined)
  const progressPollRef = useRef<number | undefined>(undefined)
  const analysisTimeoutRef = useRef<number | undefined>(undefined)
  const requestIdRef = useRef<string | undefined>(undefined)
  const abortMessageRef = useRef<string | undefined>(undefined)
  const dragDepthRef = useRef(0)
  const previewRef = useRef<string | undefined>(undefined)
  const [file, setFile] = useState<File>()
  const [previewUrl, setPreviewUrl] = useState<string>()
  const [settings, setSettings] = useState<AnalysisSettings>(DEFAULT_SETTINGS)
  const [settingsDirty, setSettingsDirty] = useState(false)
  const [progress, setProgress] = useState<AnalysisProgress>()
  const [result, setResult] = useState<AnalysisResult>()
  const [selected, setSelected] = useState<DetectedObject>()
  const [error, setError] = useState<string>()
  const [notice, setNotice] = useState<string>()
  const [showSkyMap, setShowSkyMap] = useState(false)
  const [externalDragging, setExternalDragging] = useState(false)

  useEffect(() => () => {
    const activeRequest = requestIdRef.current
    abortRef.current?.abort()
    if (activeRequest) void cancelAnalysis(activeRequest).catch(() => undefined)
    if (progressPollRef.current) window.clearTimeout(progressPollRef.current)
    if (analysisTimeoutRef.current) window.clearTimeout(analysisTimeoutRef.current)
    if (previewRef.current) URL.revokeObjectURL(previewRef.current)
  }, [])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(undefined), 4200)
    return () => window.clearTimeout(timer)
  }, [notice])

  const openPicker = () => inputRef.current?.click()

  const stopProgressPolling = () => {
    if (progressPollRef.current) window.clearTimeout(progressPollRef.current)
    progressPollRef.current = undefined
  }

  const stopAnalysisTimeout = () => {
    if (analysisTimeoutRef.current) window.clearTimeout(analysisTimeoutRef.current)
    analysisTimeoutRef.current = undefined
  }

  const startProgressPolling = (activeRequest: string, controller: AbortController, startedAt: number) => {
    stopProgressPolling()
    const poll = async () => {
      if (controller.signal.aborted || requestIdRef.current !== activeRequest) return
      const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
      setProgress((current) => current ? { ...current, elapsedSeconds } : current)
      try {
        const latest = await getAnalysisProgress(activeRequest, controller.signal)
        if (latest && !controller.signal.aborted && requestIdRef.current === activeRequest) {
          setProgress(progressFromServer(latest, elapsedSeconds))
        }
      } catch (caught) {
        if (controller.signal.aborted) return
        // Progress is an auxiliary channel. The analysis response remains the
        // source of truth, so a single missed heartbeat must not fail the job.
        console.debug('识别进度暂时不可用', caught)
      }
      if (!controller.signal.aborted && requestIdRef.current === activeRequest) {
        progressPollRef.current = window.setTimeout(() => void poll(), PROGRESS_POLL_MS)
      }
    }
    void poll()
  }

  const runAnalysis = async (nextFile: File, nextPreview?: string) => {
    const previousRequest = requestIdRef.current
    abortRef.current?.abort()
    if (previousRequest) void cancelAnalysis(previousRequest).catch(() => undefined)
    stopProgressPolling()
    stopAnalysisTimeout()
    const controller = new AbortController()
    const activeRequest = requestId()
    const startedAt = Date.now()
    abortRef.current = controller
    requestIdRef.current = activeRequest
    abortMessageRef.current = undefined
    setError(undefined)
    setNotice(undefined)
    const requestedSettings = settings
    setProgress(initialProgress())
    startProgressPolling(activeRequest, controller, startedAt)
    analysisTimeoutRef.current = window.setTimeout(() => {
      if (requestIdRef.current !== activeRequest || controller.signal.aborted) return
      const message = '识别超过 5 分钟，已自动取消。请检查照片是否完整，或重试一次。'
      abortMessageRef.current = message
      void cancelAnalysis(activeRequest).catch(() => undefined)
      controller.abort()
      stopProgressPolling()
      setProgress(undefined)
      setError(message)
    }, ANALYSIS_TIMEOUT_MS)
    try {
      const dimensionsPromise = nextPreview
        ? getImageDimensionsBounded(nextPreview)
        : Promise.resolve({ width: undefined, height: undefined })
      const [analysis, dimensions] = await Promise.all([
        analyzePhoto(nextFile, requestedSettings, activeRequest, controller.signal),
        dimensionsPromise,
      ])
      if (controller.signal.aborted || requestIdRef.current !== activeRequest) return
      const withDimensions: AnalysisResult = {
        ...analysis,
        metadata: {
          ...analysis.metadata,
          width: analysis.metadata.width ?? dimensions.width,
          height: analysis.metadata.height ?? dimensions.height,
        },
      }
      stopProgressPolling()
      stopAnalysisTimeout()
      setProgress(undefined)
      setResult(withDimensions)
      setSettingsDirty(false)
      // Keep the solved frame visible on first render. The user can click any
      // catalogue entry to inspect it without losing the full-field overview.
      setSelected(undefined)
    } catch (caught) {
      stopProgressPolling()
      stopAnalysisTimeout()
      setProgress(undefined)
      if (controller.signal.aborted) {
        if (requestIdRef.current === activeRequest && abortMessageRef.current) setError(abortMessageRef.current)
        return
      }
      if (requestIdRef.current !== activeRequest) return
      setError(caught instanceof Error ? caught.message : '识别过程中出现未知错误，请稍后重试。')
    } finally {
      if (requestIdRef.current === activeRequest) {
        requestIdRef.current = undefined
        abortRef.current = undefined
        abortMessageRef.current = undefined
        stopProgressPolling()
        stopAnalysisTimeout()
      }
    }
  }

  const chooseFile = async (incomingFile: File) => {
    if (progress) {
      setNotice('请先取消当前识别，再拖入另一张照片。')
      return
    }
    try {
      const nextFile = await normalizeIncomingFile(incomingFile)
      const validationError = validatePhoto(nextFile)
      if (validationError) {
        setError(validationError)
        return
      }
      if (previewRef.current) URL.revokeObjectURL(previewRef.current)
      const nextPreview = URL.createObjectURL(nextFile)
      previewRef.current = nextPreview
      setPreviewUrl(nextPreview)
      setFile(nextFile)
      setResult(undefined)
      setSelected(undefined)
      setShowSkyMap(false)
      void runAnalysis(nextFile, nextPreview)
    } catch {
      setError(INCOMING_FILE_READ_ERROR)
    }
  }

  const reanalyze = () => {
    if (file) void runAnalysis(file, previewUrl)
  }

  const cancelCurrentAnalysis = () => {
    const activeRequest = requestIdRef.current
    if (!activeRequest) return
    const message = '识别已取消，原照片仍保留，可直接重新尝试。'
    abortMessageRef.current = message
    void cancelAnalysis(activeRequest).catch(() => undefined)
    abortRef.current?.abort()
    stopProgressPolling()
    stopAnalysisTimeout()
    setProgress(undefined)
    setError(message)
  }

  useEffect(() => {
    const onDragEnter = (event: DragEvent) => {
      event.preventDefault()
      if (!transferCarriesFiles(event.dataTransfer)) return
      dragDepthRef.current += 1
      if (!progress) setExternalDragging(true)
    }
    const onDragOver = (event: DragEvent) => {
      event.preventDefault()
      if (event.dataTransfer && transferCarriesFiles(event.dataTransfer)) event.dataTransfer.dropEffect = 'copy'
    }
    const onDragLeave = (event: DragEvent) => {
      event.preventDefault()
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
      if (dragDepthRef.current === 0) setExternalDragging(false)
    }
    const resetDragState = () => {
      dragDepthRef.current = 0
      setExternalDragging(false)
    }
    const onDrop = async (event: DragEvent) => {
      event.preventDefault()
      dragDepthRef.current = 0
      setExternalDragging(false)
      if (progress) {
        setNotice('请先取消当前识别，再拖入另一张照片。')
        return
      }
      try {
        const candidate = await firstSupportedFileFromTransfer(event.dataTransfer)
        if (candidate) {
          await chooseFile(candidate)
          return
        }
        setError(INCOMING_FILE_UNSUPPORTED_ERROR)
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : INCOMING_FILE_READ_ERROR)
      }
    }
    const onPaste = async (event: ClipboardEvent) => {
      if (!transferCarriesFiles(event.clipboardData)) return
      event.preventDefault()
      if (progress) {
        setNotice('请先取消当前识别，再粘贴另一张照片。')
        return
      }
      try {
        const candidate = await firstSupportedFileFromTransfer(event.clipboardData)
        if (candidate) await chooseFile(candidate)
        else setError(INCOMING_FILE_UNSUPPORTED_ERROR)
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : INCOMING_FILE_READ_ERROR)
      }
    }
    window.addEventListener('dragenter', onDragEnter)
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('dragend', resetDragState)
    window.addEventListener('drop', onDrop)
    window.addEventListener('paste', onPaste)
    return () => {
      window.removeEventListener('dragenter', onDragEnter)
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('dragend', resetDragState)
      window.removeEventListener('drop', onDrop)
      window.removeEventListener('paste', onPaste)
    }
  }, [progress, settings])

  const hasCoordinateOverlay = Boolean(result?.objects.some((object) =>
    (object.x !== undefined && object.y !== undefined) || object.lines?.length,
  ))
  const overlayBackground = result?.originalImage ?? previewUrl
  const canvasSource = useMemo(
    () => hasCoordinateOverlay && overlayBackground ? overlayBackground : result?.annotatedImage ?? overlayBackground,
    [hasCoordinateOverlay, overlayBackground, result?.annotatedImage],
  )

  const updateSettings = (nextSettings: AnalysisSettings) => {
    const requiresAnalysis = nextSettings.deepSky.value !== settings.deepSky.value
      || nextSettings.brightStars.value !== settings.brightStars.value
      || nextSettings.catalogDepth !== settings.catalogDepth
      || nextSettings.labelDensity !== settings.labelDensity
    setSettings(nextSettings)
    if (result && requiresAnalysis) {
      setSettingsDirty(true)
      setNotice('阈值或目录设置已更改，请点击「重新识别」应用。')
    }
  }

  const downloadAnnotated = async () => {
    if (!result) return
    try {
      if (settingsDirty) {
        setNotice('请先点击「重新识别」应用新阈值，再下载标注图。')
        return
      }
      setNotice('正在准备高分辨率标注图…')
      const visibleObjects = selectOverlayObjects(result.objects, settings)
      const coordinateSize = { width: result.metadata.width, height: result.metadata.height }
      let blob: Blob
      if (hasCoordinateOverlay && previewUrl) blob = await createAnnotatedBlob(previewUrl, visibleObjects, settings, coordinateSize)
      else if (hasCoordinateOverlay && result.originalImage) blob = await createAnnotatedBlob(result.originalImage, visibleObjects, settings, coordinateSize)
      else if (result.downloadUrl) blob = await sourceToBlob(result.downloadUrl)
      else if (result.annotatedImage) blob = await sourceToBlob(result.annotatedImage)
      else if (canvasSource) blob = await createAnnotatedBlob(canvasSource, visibleObjects, settings, coordinateSize)
      else throw new Error('当前没有可下载的标注图')
      const base = result.metadata.filename.replace(/\.[^.]+$/, '') || 'starfield'
      downloadBlob(blob, `${base}-annotated.png`)
      setNotice('标注图已开始下载')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '下载标注图失败')
    }
  }

  const exportObjects = async () => {
    if (!result) return
    try {
      if (result.resultsUrl) {
        const blob = await sourceToBlob(result.resultsUrl)
        const base = result.metadata.filename.replace(/\.[^.]+$/, '') || 'starfield'
        downloadBlob(blob, `${base}-objects.json`)
      } else {
        exportResultJson(result, settings)
      }
      setNotice('天体清单已开始下载')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '导出天体清单失败')
    }
  }

  return (
    <div className="app-shell">
      <Header
        hasFile={Boolean(file)}
        hasResult={Boolean(result)}
        analyzing={Boolean(progress && progress.percent < 100)}
        settingsDirty={settingsDirty}
        onUpload={openPicker}
        onReanalyze={reanalyze}
        onCancel={cancelCurrentAnalysis}
        onDownload={() => void downloadAnnotated()}
        onExport={() => void exportObjects()}
      />
      <input
        ref={inputRef}
        hidden
        type="file"
        tabIndex={-1}
        aria-hidden="true"
        accept=".jpg,.jpeg,.png,.tif,.tiff,image/jpeg,image/png,image/tiff"
        onChange={(event) => {
          const nextFile = event.target.files?.item(0)
          if (nextFile) void chooseFile(nextFile)
          event.target.value = ''
        }}
      />
      {externalDragging && (
        <div className="external-drop-overlay" role="status" aria-live="polite">
          <div className="external-drop-overlay__card">
            <strong>松开即可识别这张照片</strong>
            <span>支持从资源管理器、微信临时文件直接拖入</span>
            <small>微信虚拟附件也可复制后按 Ctrl+V 粘贴</small>
          </div>
        </div>
      )}
      {result ? (
        <main className="result-layout">
          <StarCanvas
            result={result}
            settings={settings}
            source={canvasSource}
            renderOverlay={hasCoordinateOverlay && Boolean(overlayBackground)}
            selected={selected}
            progress={progress}
            onBrowse={openPicker}
            onFile={chooseFile}
            onSelect={setSelected}
          />
          <ResultSidebar
            result={result}
            settings={settings}
            selectedId={selected?.id}
            imageSource={overlayBackground}
            settingsDirty={settingsDirty}
            onSettingsChange={updateSettings}
            onApplySettings={reanalyze}
            onSelect={setSelected}
            onOpenSkyMap={() => setShowSkyMap(true)}
          />
        </main>
      ) : (
        <UploadScreen
          settings={settings}
          progress={progress}
          error={error}
          filename={file?.name}
          onSettingsChange={updateSettings}
          onBrowse={openPicker}
          onFile={chooseFile}
        onRetry={reanalyze}
        onCancel={cancelCurrentAnalysis}
        onIncomingError={setError}
      />
      )}
      {result && error && (
        <div className="toast toast--error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError(undefined)} aria-label="关闭错误提示"><CloseIcon /></button>
        </div>
      )}
      {notice && (
        <div className="toast" role="status">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(undefined)} aria-label="关闭提示"><CloseIcon /></button>
        </div>
      )}
      {result && showSkyMap && <SkyMapDialog result={result} onClose={() => setShowSkyMap(false)} />}
    </div>
  )
}

export default App
