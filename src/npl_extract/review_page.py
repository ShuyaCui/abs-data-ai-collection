"""Render an offline human-review page from immutable candidate facts."""

from __future__ import annotations

import json
from typing import Any


def render_review_page(facts: list[dict[str, Any]], field_names: dict[str, str]) -> str:
    """Return one self-contained HTML page; browser actions create drafts only."""
    payload = json.dumps(
        {"facts": facts, "field_names": field_names},
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    count = len(facts)
    cashflow_facts = [fact for fact in facts if fact.get("field_id") == "cashflow_collection_table"]
    cashflow_notice = (
        "现金流归集表的单元格证据已就绪，可按月份、金额、占比及合计复核。"
        if cashflow_facts and all(fact.get("evidence") for fact in cashflow_facts)
        else "现金流归集表的单元格证据不完整；不得接受或导出为正式确认。"
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NPL PDF 人工复核队列</title>
<style>
  :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f6f7fb; }}
  body {{ margin: 0; }} main {{ max-width: 1180px; margin: auto; padding: 28px 20px 64px; }}
  h1 {{ margin: 0; font-size: 26px; }} .sub {{ color: #586174; margin: 8px 0 20px; }}
  .notice {{ background: #fff8db; border: 1px solid #ead78a; border-radius: 10px; padding: 12px 14px; line-height: 1.5; }}
  .controls {{ display: grid; grid-template-columns: 1.5fr 1fr 1fr auto; gap: 10px; margin: 18px 0; }}
  input, select, textarea, button {{ font: inherit; border: 1px solid #cbd2df; border-radius: 8px; padding: 9px 10px; background: white; }}
  button {{ cursor: pointer; background: #0b5cad; color: white; border-color: #0b5cad; font-weight: 600; }}
  button:hover {{ background: #084a8c; }} #count {{ color: #586174; margin: 8px 0; }}
  .card {{ background: white; border: 1px solid #dce1ea; border-radius: 12px; margin: 12px 0; overflow: hidden; }}
  .fact {{ display: grid; grid-template-columns: minmax(190px, 1fr) minmax(180px, 1fr) 130px; gap: 12px; padding: 16px; align-items: start; }}
  .field {{ font-weight: 700; }} .value {{ font-size: 17px; word-break: break-word; }} .meta, .evidence-meta {{ color: #586174; font-size: 13px; line-height: 1.5; }}
  .status {{ display: inline-block; font-size: 12px; border-radius: 999px; padding: 3px 8px; background: #e8f1ff; color: #084a8c; }}
  details {{ border-top: 1px solid #e4e7ee; padding: 12px 16px; }} summary {{ cursor: pointer; font-weight: 600; }}
  .evidence {{ border-left: 3px solid #8bb6e9; padding: 8px 12px; margin: 10px 0; background: #f7fbff; }} .source {{ font-weight: 600; }} .quote {{ white-space: pre-wrap; margin-top: 5px; }}
  .decision {{ display: grid; grid-template-columns: 150px 220px 1fr; gap: 10px; padding: 14px 16px 16px; background: #f9fafc; border-top: 1px solid #e4e7ee; }}
  .decision textarea {{ min-height: 40px; resize: vertical; }} .footer {{ margin-top: 16px; color: #586174; font-size: 13px; }}
  @media (max-width: 760px) {{ .controls, .fact, .decision {{ grid-template-columns: 1fr; }} main {{ padding: 18px 12px 40px; }} }}
</style>
<main>
  <h1>PDF 抽取人工复核队列</h1>
  <p class="sub">{count} 条候选/支撑事实。页面离线运行；导出的是复核草稿，不会写入 confirmed facts。</p>
  <div class="notice">{cashflow_notice} 对每条候选，先核对全部原文证据，再填写决定。</div>
  <section class="controls" aria-label="筛选与导出">
    <input id="search" type="search" placeholder="搜索字段、实体、值或证据原文">
    <select id="entity"><option value="">全部实体</option></select>
    <select id="status"><option value="">全部状态</option></select>
    <button id="export" type="button">导出复核草稿</button>
  </section>
  <div id="count"></div>
  <label class="meta" for="reviewer">复核人 ID（导出时必填）</label>
  <input id="reviewer" placeholder="例如 business-owner:zhangsan" style="width:min(420px,100%);display:block;margin:6px 0 18px">
  <section id="facts" aria-live="polite"></section>
  <p class="footer">导出的草稿供复核人留档或据此调用现有 <code>npl-extract review</code>。它不替代不可变 ReviewDecision，也不会自动确认事实。</p>
</main>
<script>
const data = {payload};
const decisions = new Map();
const el = (tag, text, className) => {{ const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }};
const valueText = (value) => Array.isArray(value) ? value.join('；') : value && typeof value === 'object' ? JSON.stringify(value) : String(value ?? '');
const search = document.querySelector('#search'); const entity = document.querySelector('#entity'); const status = document.querySelector('#status'); const list = document.querySelector('#facts');
for (const key of [...new Set(data.facts.map((fact) => fact.entity_key))].sort()) entity.append(new Option(key, key));
for (const key of [...new Set(data.facts.map((fact) => fact.status))].sort()) status.append(new Option(key, key));
function matchingText(fact) {{ return [data.field_names[fact.field_id] || fact.field_id, fact.entity_key, valueText(fact.value), ...fact.evidence.map((e) => [e.document_name, e.locator, e.exact_text].join(' '))].join(' ').toLowerCase(); }}
function updateDecision(fact, name, value) {{ const current = decisions.get(fact.fact_id) || {{ fact_id: fact.fact_id, field_id: fact.field_id, entity_key: fact.entity_key }}; current[name] = value; decisions.set(fact.fact_id, current); }}
function render() {{
  const term = search.value.trim().toLowerCase(); const shown = data.facts.filter((fact) => (!term || matchingText(fact).includes(term)) && (!entity.value || fact.entity_key === entity.value) && (!status.value || fact.status === status.value));
  list.replaceChildren(); document.querySelector('#count').textContent = `显示 ${{shown.length}} / ${{data.facts.length}} 条候选事实`;
  for (const fact of shown) {{
    const card = el('article', undefined, 'card'); const summary = el('section', undefined, 'fact');
    const left = el('div'); left.append(el('div', data.field_names[fact.field_id] || fact.field_id, 'field')); left.append(el('div', fact.field_id, 'meta')); left.append(el('div', fact.entity_key, 'meta')); summary.append(left);
    const middle = el('div'); middle.append(el('div', valueText(fact.value), 'value')); middle.append(el('div', fact.effective_at ? `生效日：${{fact.effective_at}}` : '静态事实 / 未指定生效日', 'meta')); summary.append(middle);
    const right = el('div'); right.append(el('span', fact.status, 'status')); right.append(el('div', `证据 ${{fact.evidence.length}} 条`, 'meta')); summary.append(right); card.append(summary);
    const details = el('details'); details.append(el('summary', `查看全部 ${{fact.evidence.length}} 条证据`));
    for (const evidence of fact.evidence) {{ const box = el('div', undefined, 'evidence'); box.append(el('div', `${{evidence.document_name}}｜p${{evidence.physical_page}}`, 'source')); box.append(el('div', `${{evidence.locator}}｜${{evidence.evidence_id}}`, 'evidence-meta')); box.append(el('div', evidence.exact_text, 'quote')); details.append(box); }} card.append(details);
    const decision = el('section', undefined, 'decision'); const saved = decisions.get(fact.fact_id) || {{}};
    const action = document.createElement('select'); action.append(new Option('待决定', '')); for (const item of ['accept', 'correct', 'reject']) action.append(new Option(item, item)); action.value = saved.action || ''; action.addEventListener('change', () => updateDecision(fact, 'action', action.value)); decision.append(action);
    const reason = document.createElement('input'); reason.placeholder = '原因码，例如 VALUE_AND_EVIDENCE_CONFIRMED'; reason.value = saved.reason_code || ''; reason.addEventListener('input', () => updateDecision(fact, 'reason_code', reason.value)); decision.append(reason);
    const note = document.createElement('textarea'); note.placeholder = '复核意见；若选择 correct，请写明更正值与依据（正式更正仍需独立 corrected fact）'; note.value = saved.note || ''; note.addEventListener('input', () => updateDecision(fact, 'note', note.value)); decision.append(note); card.append(decision); list.append(card);
  }}
}}
search.addEventListener('input', render); entity.addEventListener('change', render); status.addEventListener('change', render);
document.querySelector('#export').addEventListener('click', () => {{
  const reviewer_id = document.querySelector('#reviewer').value.trim(); const rows = [...decisions.values()].filter((row) => row.action);
  if (!reviewer_id) return alert('请先填写复核人 ID。'); if (!rows.length) return alert('请至少选择一条复核决定。');
  const blob = new Blob([JSON.stringify({{ reviewer_id, exported_at: new Date().toISOString(), kind: 'review_draft', decisions: rows }}, null, 2)], {{ type: 'application/json' }});
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'mvp-v0-review-draft.json'; link.click(); URL.revokeObjectURL(link.href);
}});
render();
</script>
</html>"""


def write_review_page(facts_path: str, fields_path: str, output_path: str) -> None:
    """Read the existing JSONL/contracts and write the local review page."""
    with open(facts_path, encoding="utf-8") as source:
        facts = [json.loads(line) for line in source if line.strip()]
    with open(fields_path, encoding="utf-8") as source:
        fields = json.load(source)
    names = {field["id"]: field["export_name"] for group in ("fields", "supporting_fields") for field in fields.get(group, [])}
    with open(output_path, "w", encoding="utf-8") as output:
        output.write(render_review_page(facts, names))
