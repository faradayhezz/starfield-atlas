export const RAW_IMAGE_EXTENSIONS = ['arw', 'cr2', 'cr3', 'nef', 'nrw', 'dng', 'raf', 'orf', 'rw2', 'pef', 'srw', 'raw', 'sr2', 'srf', '3fr', 'fff', 'iiq', 'rwl', 'mos', 'mrw', 'kdc', 'dcr', 'erf', 'mef', 'mdc', 'x3f'] as const
export const SUPPORTED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'tif', 'tiff', ...RAW_IMAGE_EXTENSIONS] as const
export const IMAGE_FILE_ACCEPT = SUPPORTED_IMAGE_EXTENSIONS.map((extension) => `.${extension}`).join(',')
export const canPreviewImageFile = (file: File): boolean => /\.(jpe?g|png)$/i.test(file.name)

export const INCOMING_FILE_READ_ERROR = '无法读取拖入的图片数据。微信虚拟附件可先复制图片，再按 Ctrl+V 粘贴。'
export const INCOMING_FILE_UNSUPPORTED_ERROR = '没有读取到支持的 JPG、PNG、TIFF 或相机 RAW 文件。微信虚拟附件可复制图片后按 Ctrl+V 粘贴。'

interface ImageFormat {
  extension: 'jpg' | 'png' | 'tiff'
  mime: 'image/jpeg' | 'image/png' | 'image/tiff'
}

const MIME_FORMATS: Record<string, ImageFormat> = {
  'image/jpeg': { extension: 'jpg', mime: 'image/jpeg' },
  'image/jpg': { extension: 'jpg', mime: 'image/jpeg' },
  'image/pjpeg': { extension: 'jpg', mime: 'image/jpeg' },
  'image/png': { extension: 'png', mime: 'image/png' },
  'image/x-png': { extension: 'png', mime: 'image/png' },
  'image/tiff': { extension: 'tiff', mime: 'image/tiff' },
  'image/tif': { extension: 'tiff', mime: 'image/tiff' },
  'image/x-tiff': { extension: 'tiff', mime: 'image/tiff' },
}

const extensionOf = (filename: string): string => filename.split('.').pop()?.toLowerCase() ?? ''

export const hasSupportedImageExtension = (filename: string): boolean => (
  SUPPORTED_IMAGE_EXTENSIONS.includes(extensionOf(filename) as typeof SUPPORTED_IMAGE_EXTENSIONS[number])
)

const imageFormatFromBytes = async (file: File): Promise<ImageFormat | undefined> => {
  const bytes = new Uint8Array(await file.slice(0, 12).arrayBuffer())
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return { extension: 'jpg', mime: 'image/jpeg' }
  if (bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) return { extension: 'png', mime: 'image/png' }
  const littleTiff = bytes[0] === 0x49 && bytes[1] === 0x49 && bytes[2] === 0x2a && bytes[3] === 0x00
  const bigTiff = bytes[0] === 0x4d && bytes[1] === 0x4d && bytes[2] === 0x00 && bytes[3] === 0x2a
  if (littleTiff || bigTiff) return { extension: 'tiff', mime: 'image/tiff' }
  return undefined
}

export const normalizeIncomingFile = async (file: File): Promise<File> => {
  if (hasSupportedImageExtension(file.name)) return file
  const detected = MIME_FORMATS[file.type.toLowerCase()] ?? await imageFormatFromBytes(file)
  if (!detected) return file
  const rawBase = file.name.replace(/\.[^.]+$/, '').trim()
  const base = rawBase && rawBase !== file.name ? rawBase : `微信图片-${Date.now()}`
  return new File([file], `${base}.${detected.extension}`, {
    type: detected.mime,
    lastModified: file.lastModified || Date.now(),
  })
}

const snapshotTransferFiles = (data: DataTransfer | null): File[] => {
  if (!data) return []
  const candidates: File[] = Array.from(data.files)
  for (const item of Array.from(data.items)) {
    if (item.kind !== 'file') continue
    const candidate = item.getAsFile()
    if (candidate) candidates.push(candidate)
  }
  const seen = new Set<string>()
  return candidates.filter((candidate) => {
    const key = `${candidate.name}\u0000${candidate.size}\u0000${candidate.type}\u0000${candidate.lastModified}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export const transferCarriesFiles = (data: DataTransfer | null): boolean => Boolean(
  data && (Array.from(data.types).includes('Files') || Array.from(data.items).some((item) => item.kind === 'file')),
)

export const firstSupportedFileFromTransfer = async (data: DataTransfer | null): Promise<File | undefined> => {
  // Snapshot File objects before the event handler yields. Browsers protect the
  // drag data store again after the drop/paste event has finished dispatching.
  const candidates = snapshotTransferFiles(data)
  let readFailed = false
  for (const candidate of candidates) {
    if (candidate.size <= 0) continue
    try {
      const normalized = await normalizeIncomingFile(candidate)
      if (hasSupportedImageExtension(normalized.name)) return normalized
    } catch {
      readFailed = true
    }
  }
  if (readFailed) throw new Error(INCOMING_FILE_READ_ERROR)
  return undefined
}
