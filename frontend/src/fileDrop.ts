import { transferCarriesFiles } from './incomingFile'

export interface FileDropOptions {
  onActiveChange: (active: boolean) => void
  onDrop: (data: DataTransfer | null) => void
  canDrop: () => boolean
}

/** One capture-phase owner for external files, including drops on nested UI. */
export function installFileDropHandlers(target: Window, options: FileDropOptions) {
  let depth = 0
  let active = false
  let heartbeat: number | undefined
  const setActive = (next: boolean) => {
    if (active === next) return
    active = next
    options.onActiveChange(next)
  }
  const reset = () => {
    depth = 0
    if (heartbeat !== undefined) target.clearTimeout(heartbeat)
    heartbeat = undefined
    setActive(false)
  }
  const refresh = () => {
    if (heartbeat !== undefined) target.clearTimeout(heartbeat)
    // Some external applications omit dragend/dragleave after cancellation.
    // A real drag continues to emit dragover while the pointer is stationary.
    heartbeat = target.setTimeout(reset, 1500)
  }
  const enter = (event: DragEvent) => {
    if (!transferCarriesFiles(event.dataTransfer)) return
    event.preventDefault()
    depth += 1
    setActive(options.canDrop())
    refresh()
  }
  const over = (event: DragEvent) => {
    if (!transferCarriesFiles(event.dataTransfer)) return
    event.preventDefault()
    if (event.dataTransfer) event.dataTransfer.dropEffect = options.canDrop() ? 'copy' : 'none'
    depth = Math.max(1, depth)
    setActive(options.canDrop())
    refresh()
  }
  const leave = (event: DragEvent) => {
    if (!active && !depth) return
    depth = Math.max(0, depth - 1)
    const outside = event.clientX <= 0 || event.clientY <= 0 || event.clientX >= target.innerWidth || event.clientY >= target.innerHeight
    if (depth === 0 || outside) reset()
  }
  const drop = (event: DragEvent) => {
    reset()
    if (!transferCarriesFiles(event.dataTransfer)) return
    event.preventDefault()
    event.stopPropagation()
    // Synchronously pass the data so the caller snapshots files before await.
    // It is also responsible for the explicit busy-state explanation.
    options.onDrop(event.dataTransfer)
  }
  const keydown = (event: KeyboardEvent) => { if (event.key === 'Escape') reset() }
  const visibility = () => { if (target.document.hidden) reset() }

  target.addEventListener('dragenter', enter, true)
  target.addEventListener('dragover', over, true)
  target.addEventListener('dragleave', leave, true)
  target.addEventListener('drop', drop, true)
  target.addEventListener('dragend', reset, true)
  target.addEventListener('keydown', keydown, true)
  target.addEventListener('pointerdown', reset, true)
  target.addEventListener('blur', reset)
  target.addEventListener('focus', reset)
  target.document.addEventListener('visibilitychange', visibility)
  return {
    reset,
    dispose() {
      reset()
      target.removeEventListener('dragenter', enter, true)
      target.removeEventListener('dragover', over, true)
      target.removeEventListener('dragleave', leave, true)
      target.removeEventListener('drop', drop, true)
      target.removeEventListener('dragend', reset, true)
      target.removeEventListener('keydown', keydown, true)
      target.removeEventListener('pointerdown', reset, true)
      target.removeEventListener('blur', reset)
      target.removeEventListener('focus', reset)
      target.document.removeEventListener('visibilitychange', visibility)
    },
  }
}
