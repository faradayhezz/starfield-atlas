import { useRef } from 'react'
import { BrandMark, CloseIcon, DownloadIcon, FileIcon, MoreIcon, RefreshIcon, UploadIcon } from './Icons'

interface HeaderProps {
  hasFile: boolean
  hasResult: boolean
  analyzing: boolean
  settingsDirty?: boolean
  onUpload: () => void
  onReanalyze: () => void
  onCancel: () => void
  onDownload: () => void
  onExport: () => void
}

export function Header({ hasFile, hasResult, analyzing, settingsDirty = false, onUpload, onReanalyze, onCancel, onDownload, onExport }: HeaderProps) {
  const mobileMenuRef = useRef<HTMLDetailsElement>(null)
  const reanalyzeLabel = analyzing
    ? '取消当前识别'
    : settingsDirty
      ? '有待应用的识别设置，点击应用并重新识别'
      : '重新识别当前照片'

  const exportFromMobileMenu = () => {
    onExport()
    if (mobileMenuRef.current) mobileMenuRef.current.open = false
  }

  return (
    <header className="app-header">
      <a className="brand" href="/" aria-label="星图寻迹首页">
        <BrandMark />
        <span>星图寻迹</span>
      </a>
      <nav className="header-actions" aria-label="照片操作">
        <button className="header-button" type="button" onClick={onUpload} disabled={analyzing}>
          <UploadIcon />
          <span>上传照片</span>
        </button>
        <button
          className={`header-button ${settingsDirty ? 'has-pending-settings' : ''}`}
          type="button"
          onClick={analyzing ? onCancel : onReanalyze}
          disabled={!hasFile && !analyzing}
          aria-label={reanalyzeLabel}
          title={reanalyzeLabel}
        >
          {analyzing ? <CloseIcon /> : <RefreshIcon />}
          <span>{analyzing ? '取消识别' : '重新识别'}</span>
        </button>
        <button className={`header-button ${hasResult ? 'header-button--primary' : ''}`} type="button" onClick={onDownload} disabled={!hasResult || analyzing}>
          <DownloadIcon />
          <span>下载标注图</span>
        </button>
        <button className="header-button desktop-export-action" type="button" onClick={onExport} disabled={!hasResult || analyzing}>
          <FileIcon />
          <span>导出天体清单</span>
        </button>
        <details className="mobile-more-menu" ref={mobileMenuRef}>
          <summary role="button" aria-label="更多操作" title="更多操作">
            <MoreIcon />
          </summary>
          <div className="mobile-more-menu__panel">
            <button type="button" onClick={exportFromMobileMenu} disabled={!hasResult || analyzing}>
              <FileIcon />
              <span>导出天体清单</span>
            </button>
          </div>
        </details>
      </nav>
    </header>
  )
}
