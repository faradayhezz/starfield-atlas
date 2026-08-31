import type { ReactNode } from 'react'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: ReactNode
  description?: string
  color?: 'green' | 'gold' | 'purple'
  disabled?: boolean
}

export function Toggle({ checked, onChange, label, description, color = 'green', disabled }: ToggleProps) {
  return (
    <label className={`toggle-row toggle-row--${color} ${disabled ? 'is-disabled' : ''}`}>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} disabled={disabled} />
      <span className="toggle-track" aria-hidden="true"><span /></span>
      <span className="toggle-copy">
        <span className="toggle-label">{label}</span>
        {description && <span className="toggle-description">{description}</span>}
      </span>
    </label>
  )
}
