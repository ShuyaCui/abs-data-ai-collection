import { spawn } from 'node:child_process'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'npl-document-tools'
export const inject = ['tools']

const output = {
  schema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      operation: { type: 'string', required: true },
      status: { type: 'string', required: true, enum: ['ok', 'not_found', 'review_required'] },
      result: { type: 'json', required: true },
    },
  },
  render: (_args, value) => [{ type: 'text', text: `${value.operation}: ${value.status}` }],
}
const textCalls = new WeakMap()

function approveTextEgress(config, exec) {
  if (config.allowTextEgress !== true) throw new Error('document text egress is disabled by deployment policy')
  if (!exec.agent) throw new Error('document text egress requires an agent session')
  const limit = config.maxTextCalls ?? 8
  const count = textCalls.get(exec.agent) ?? 0
  if (count >= limit) throw new Error('document text egress call limit reached')
  textCalls.set(exec.agent, count + 1)
}

function runWorker(config, operation, args, signal) {
  return new Promise((resolve, reject) => {
    const child = spawn(config.python, [config.worker, operation], { stdio: ['pipe', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    const abort = () => child.kill()
    signal.addEventListener('abort', abort, { once: true })
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', reject)
    child.on('close', (code) => {
      signal.removeEventListener('abort', abort)
      if (signal.aborted) return reject(new Error('document worker aborted'))
      if (code !== 0) return reject(new Error(stderr.trim() || `document worker exited ${code}`))
      try {
        resolve(JSON.parse(stdout))
      } catch {
        reject(new Error('document worker returned invalid JSON'))
      }
    })
    child.stdin.end(JSON.stringify(args))
  })
}

function tool(name, description, parameters, concurrencySafe, returnsText = false) {
  return (config) => defineTool({
    name,
    description,
    parameters,
    output,
    isConcurrencySafe: () => concurrencySafe,
    execute: (args, exec) => {
      if (name === 'extract_field_facts' || name === 'validate_facts') {
        if (config.allowTextEgress === true) approveTextEgress(config, exec)
        return runWorker(config, name, { ...args, redact_evidence_text: config.allowTextEgress !== true, max_text_chars: config.maxTextChars ?? 1200 }, exec.signal)
      }
      if (!returnsText) return runWorker(config, name, args, exec.signal)
      approveTextEgress(config, exec)
      return runWorker(config, name, { ...args, max_text_chars: config.maxTextChars ?? 1200 }, exec.signal)
    },
  })
}

export function apply(ctx, config) {
  const withHash = { document_sha256: { type: 'string', required: true, description: 'SHA-256 of one staged document.' } }
  ctx.tools.register(tool('retrieve_evidence', 'Retrieve one immutable evidence block by scope and ID.', { ...withHash, scope: { type: 'string', required: true }, evidence_id: { type: 'string', required: true } }, true, true)(config))
  ctx.tools.register(tool('get_page', 'Retrieve one parsed page and its evidence blocks.', { ...withHash, scope: { type: 'string', required: true }, physical_page: { type: 'integer', required: true } }, true)(config))
  ctx.tools.register(tool('get_table', 'Retrieve metadata for one immutable parsed table by ID.', { ...withHash, scope: { type: 'string', required: true }, table_id: { type: 'string', required: true } }, true)(config))
  ctx.tools.register(tool('extract_field_facts', 'Run the deterministic extractor against a staged document.', { ...withHash, entity_key: { type: 'string', required: true }, native_parser: { type: 'string', required: true, enum: ['pypdf', 'docling', 'docling-ocr'] } }, false)(config))
  ctx.tools.register(tool('validate_facts', 'Validate immutable candidate facts against parser-owned evidence and the versioned business contract.', { ...withHash, fact_ids: { type: 'array', required: true, items: { type: 'string' } } }, true)(config))
  ctx.tools.register(tool('request_review', 'Create a review request; it never records a human decision.', { ...withHash, fact_id: { type: 'string', required: true } }, false)(config))
}

export default { name, inject, apply }
