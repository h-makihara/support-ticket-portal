import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export function loadRootEnv() {
  const path = resolve(process.cwd(), '../.env')
  if (!existsSync(path)) return

  for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/)
    if (!match || process.env[match[1]] !== undefined) continue
    const value = match[2].replace(/^("|')|("|')$/g, '')
    process.env[match[1]] = value
  }
}
