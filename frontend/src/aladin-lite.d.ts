declare module 'aladin-lite' {
  const Aladin: {
    init: Promise<void>
    aladin: (container: HTMLElement, options?: Record<string, unknown>) => unknown
    imageHiPS: (id: string, options?: Record<string, unknown>) => unknown
    graphicOverlay: (options?: Record<string, unknown>) => unknown
    polygon: (points: number[][], options?: Record<string, unknown>) => unknown
    polyline: (points: number[][], options?: Record<string, unknown>) => unknown
    catalog: (options?: Record<string, unknown>) => unknown
    source: (raDeg: number, decDeg: number, data?: Record<string, unknown>) => unknown
  }
  export default Aladin
}
