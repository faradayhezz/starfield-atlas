import type { ComponentProps } from 'react'

type IconProps = ComponentProps<'svg'>

const iconProps = (props: IconProps) => ({
  width: 20,
  height: 20,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  ...props,
})

export function UploadIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" /><path d="M5 13.5H3.8A1.8 1.8 0 0 0 2 15.3v3.4a1.8 1.8 0 0 0 1.8 1.8h16.4a1.8 1.8 0 0 0 1.8-1.8v-3.4a1.8 1.8 0 0 0-1.8-1.8H19" /></svg>
}

export function RefreshIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M20 6v5h-5" /><path d="M19.2 10A8 8 0 1 0 20 15" /></svg>
}

export function DownloadIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M12 3v12m0 0l-4-4m4 4 4-4" /><path d="M4 19.5h16" /></svg>
}

export function FileIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M6 2.8h8l4 4v14.4H6z" /><path d="M14 2.8v4h4M9 11h6M9 15h6" /></svg>
}

export function MoreIcon(props: IconProps) {
  return <svg {...iconProps(props)}><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></svg>
}

export function ImageAddIcon(props: IconProps) {
  return <svg {...iconProps(props)}><rect x="2.5" y="3" width="15.5" height="15" rx="1.8" /><circle cx="7" cy="8" r="1.2" /><path d="m3 16 4.5-4.5 3.2 3.1 3.6-4 3.7 4" /><circle cx="18" cy="18" r="4" fill="var(--surface, #161a1d)" /><path d="M18 16v4m-2-2h4" /></svg>
}

export function LockIcon(props: IconProps) {
  return <svg {...iconProps(props)}><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8.5 10V7.3a3.5 3.5 0 0 1 7 0V10" /></svg>
}

export function ChevronRightIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="m9 5 7 7-7 7" /></svg>
}

export function CheckIcon(props: IconProps) {
  return <svg {...iconProps(props)}><circle cx="12" cy="12" r="9" /><path d="m8 12 2.6 2.6L16.5 9" /></svg>
}

export function ZoomInIcon(props: IconProps) {
  return <svg {...iconProps(props)}><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.5 15.5 5 5M10.5 7.5v6m-3-3h6" /></svg>
}

export function ZoomOutIcon(props: IconProps) {
  return <svg {...iconProps(props)}><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.5 15.5 5 5M7.5 10.5h6" /></svg>
}

export function FitIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5" /></svg>
}

export function CrosshairIcon(props: IconProps) {
  return <svg {...iconProps(props)}><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /><path d="M12 2v4m0 12v4M2 12h4m12 0h4" /></svg>
}

export function AlertIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M12 3 2.8 20h18.4z" /><path d="M12 9v5m0 3h.01" /></svg>
}

export function CloseIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="m5 5 14 14M19 5 5 19" /></svg>
}

export function CameraIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M4 7h3l1.5-2h7L17 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z" /><circle cx="12" cy="13" r="4" /></svg>
}

export function LocationIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></svg>
}

export function MapIcon(props: IconProps) {
  return <svg {...iconProps(props)}><path d="m3.5 5.5 5-2.4 7 2.4 5-2.4v15.4l-5 2.4-7-2.4-5 2.4V5.5Z" /><path d="M8.5 3.1v15.4m7-13v15.4" /></svg>
}

export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 40 40">
        <rect x="1" y="1" width="38" height="38" rx="10" fill="#101819" stroke="#33433c" />
        <circle cx="20" cy="20" r="11.5" fill="none" stroke="#2bd875" strokeWidth="1.7" />
        <path d="M20 5.5v6M20 28.5v6M5.5 20h6M28.5 20h6" stroke="#718078" strokeWidth="1.4" strokeLinecap="round" />
        <path d="m20 12.3 2.1 5.6 5.6 2.1-5.6 2.1-2.1 5.6-2.1-5.6-5.6-2.1 5.6-2.1 2.1-5.6Z" fill="#f3f7f4" />
        <circle cx="31.2" cy="8.8" r="1.8" fill="#f4ce3a" />
        <path d="M29.3 10.1c-3.9 1.4-6.3 3.4-7.5 6.2" fill="none" stroke="#2bd875" strokeWidth="1.4" strokeLinecap="round" opacity=".88" />
      </svg>
    </span>
  )
}
