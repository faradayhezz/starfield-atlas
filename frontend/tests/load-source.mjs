import { readFile, access } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { transformWithOxc } from 'vite'

// Exercise the application sources without creating build artifacts or relying
// on a second TS/JSX compiler. Vite's own transformer is already a dependency.
const modules = new Map()
async function sourceModule(url) {
  if (modules.has(url.href)) return modules.get(url.href)
  const loading = (async () => {
    const { code } = await transformWithOxc(await readFile(url, 'utf8'), fileURLToPath(url))
    const imports = [...code.matchAll(/\bfrom\s*['"]([^'"]+)['"]/g)]
    let compiled = code
    for (const match of imports.reverse()) {
      let resolved
      if (match[1].startsWith('.')) {
        const base = new URL(match[1], url)
        for (const extension of ['', '.ts', '.tsx']) {
          const candidate = new URL(`${base.href}${extension}`)
          try { await access(candidate); resolved = await sourceModule(candidate); break } catch (error) {
            if (error.code !== 'ENOENT') throw error
          }
        }
        if (!resolved) throw new Error(`Unresolved test import: ${base.href}`)
      } else {
        resolved = import.meta.resolve(match[1])
      }
      const offset = match.index + match[0].indexOf(match[1])
      compiled = compiled.slice(0, offset) + resolved + compiled.slice(offset + match[1].length)
    }
    compiled += `\n//# sourceURL=${url.href}\n`
    return `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
  })()
  modules.set(url.href, loading)
  return loading
}

export async function loadSource(relativePath) {
  return import(await sourceModule(new URL(`../src/${relativePath}`, import.meta.url)))
}
