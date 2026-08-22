import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const expectedVersion = '0.1.0-rc.8'
const expectedIntegrity = 'sha512-VQU5NlomrKLRgcXuOf+sxWFvqxPA8q9vMhrKPlPPXiOJEhGlGlAdiyxZvZxkCVI+v0zbhe21cY3/luLyxpSzzA=='
const lock = JSON.parse(readFileSync(`${root}/package-lock.json`, 'utf8'))
const integrity = lock.packages?.['node_modules/@deepseek-ai/dsh']?.integrity
const version = execFileSync(`${root}/node_modules/.bin/dsh`, ['--version'], { encoding: 'utf8' }).trim()

if (version !== expectedVersion || integrity !== expectedIntegrity) throw new Error('fixed DeepSeek Harness runtime identity mismatch')
console.log(JSON.stringify({ version, integrity }))
