from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from pathlib import Path

from npl_extract.contracts import EvidenceRef, ExtractionFact, FactInput, FactStatus
from npl_extract.parsers import PageContent


@dataclass(frozen=True)
class RecoveryComponent:
    fact_id: str
    amount_cny: str
    evidence: EvidenceRef


_REPORT_DATE = re.compile(r"报告日期\s*[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_IN_PROGRESS_RECOVERY = re.compile(r"^处置中\s+[\d,]+\.\d+\s+([\d,]+\.\d+)")
_COMPLETED_RECOVERY = re.compile(r"^本期处置完毕\s+[\d,]+\.\d+\s+([\d,]+\.\d+)")
_INITIAL_CUTOFF = re.compile(r"初始起算日\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_ISSUE_TOTAL = re.compile(r"发行规模为\s*([\d,]+(?:\.\d+)?)\s*元")
_INITIAL_POOL_BALANCE = re.compile(r"资产池未偿本息\s*费余额\s*([\d,]+(?:\.\d+)?)\s*万元")
_INITIAL_POOL_SECTION = re.compile(r"资产池特征\s*[（(]\s*于初始起算日\s*[）)]")
_SECURITY_CODE = re.compile(r"^\d{7}$")
_EXPECTED_MATURITY = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")
_AMOUNT_IN_TEN_THOUSANDS = re.compile(r"^([\d,]+(?:\.\d+)?)万元$")
_FIRST_INTEREST_PAYMENT = re.compile(r"资产支持证券的第一个支付日是\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def derive_npl_recovery_cash(
    *, entity_key: str, in_progress: RecoveryComponent, completed: RecoveryComponent
) -> ExtractionFact:
    """Calculate gross NPL recovery before expenses, excluding other cash inflows."""
    total_cny = Decimal(in_progress.amount_cny) + Decimal(completed.amount_cny)
    value_cny_100m = format(total_cny / Decimal("100000000"), "f")
    return ExtractionFact(
        fact_id=f"derived:npl-recovery:{in_progress.fact_id}:{completed.fact_id}",
        field_id="npl_trustee_recovery_cash",
        entity_key=entity_key,
        status=FactStatus.DERIVED,
        value=value_cny_100m,
        evidence=[in_progress.evidence, completed.evidence],
        rule_version="npl-recovery-cash-v1",
        derived_inputs=[
            FactInput(fact_id=in_progress.fact_id, confirmed=False),
            FactInput(fact_id=completed.fact_id, confirmed=False),
        ],
    )


def extract_trustee_report_facts(
    pages: list[PageContent], document_name: str, entity_key: str, artifact_scope: str
) -> list[ExtractionFact]:
    """Extract deterministic trustee-report facts from parser-owned text blocks."""
    document_text = "\n".join(block.exact_text for page in pages for block in page.blocks)
    if "受托机构报告" not in document_name and "受托机构报告" not in document_text:
        return []
    report_date: ExtractionFact | None = None
    in_progress: RecoveryComponent | None = None
    completed: RecoveryComponent | None = None
    for page in pages:
        for block in page.blocks:
            if report_date is None and (match := _REPORT_DATE.search(block.exact_text)):
                try:
                    value = date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
                except ValueError:
                    continue
                report_date = ExtractionFact(
                    fact_id=f"disclosed:latest-report-date:{block.evidence_id}",
                    field_id="latest_report_date",
                    entity_key=entity_key,
                    status=FactStatus.DISCLOSED,
                    value=value,
                    evidence=[_evidence(block.evidence_id, artifact_scope, document_name, page.physical_page, "封面/报告日期", block.exact_text)],
                )
            if "资金池现金流流入" in document_text and in_progress is None and (match := _IN_PROGRESS_RECOVERY.search(block.exact_text)):
                in_progress = RecoveryComponent(
                    fact_id=f"disclosed:recovery-in-progress:{block.evidence_id}",
                    amount_cny=match.group(1).replace(",", ""),
                    evidence=_evidence(
                        block.evidence_id,
                        artifact_scope,
                        document_name,
                        page.physical_page,
                        "四、资产池表现情况/（三）资金池现金流流入/处置中/累计回收金额",
                        block.exact_text,
                    ),
                )
            if "资金池现金流流入" in document_text and completed is None and (match := _COMPLETED_RECOVERY.search(block.exact_text)):
                completed = RecoveryComponent(
                    fact_id=f"disclosed:recovery-completed:{block.evidence_id}",
                    amount_cny=match.group(1).replace(",", ""),
                    evidence=_evidence(
                        block.evidence_id,
                        artifact_scope,
                        document_name,
                        page.physical_page,
                        "四、资产池表现情况/（三）资金池现金流流入/本期处置完毕/累计回收金额",
                        block.exact_text,
                    ),
                )
    facts = [fact for fact in [report_date] if fact is not None]
    if in_progress and completed:
        facts.extend(
            [
                ExtractionFact(
                    fact_id=in_progress.fact_id,
                    field_id="npl_recovery_in_progress_cumulative",
                    entity_key=entity_key,
                    status=FactStatus.DISCLOSED,
                    value=in_progress.amount_cny,
                    evidence=[in_progress.evidence],
                ),
                ExtractionFact(
                    fact_id=completed.fact_id,
                    field_id="npl_recovery_completed_cumulative",
                    entity_key=entity_key,
                    status=FactStatus.DISCLOSED,
                    value=completed.amount_cny,
                    evidence=[completed.evidence],
                ),
            ]
        )
        facts.append(derive_npl_recovery_cash(entity_key=entity_key, in_progress=in_progress, completed=completed))
    return facts


def extract_issuance_announcement_facts(
    pages: list[PageContent], document_name: str, entity_key: str, artifact_scope: str
) -> list[ExtractionFact]:
    """Extract product-level facts stated directly in an issuance announcement."""
    if "发行公告" not in document_name:
        return []
    product_name = Path(document_name).stem.removesuffix("发行公告")
    if not product_name.endswith("不良资产支持证券"):
        return []
    facts: list[ExtractionFact] = []
    found: set[str] = set()
    amount_candidates = []
    initial_cutoff_candidates = []
    for page in pages:
        for index, block in enumerate(page.blocks):
            normalized = re.sub(r"\s+", "", block.exact_text)
            next_block = page.blocks[index + 1] if index + 1 < len(page.blocks) else None
            next_text = next_block.exact_text if next_block else ""
            next_normalized = re.sub(r"\s+", "", next_text)
            context = normalized + next_normalized
            title_is_split = page.physical_page == 1 and normalized == product_name and next_normalized.startswith("发行公告")
            title_is_inline = page.physical_page == 1 and normalized.startswith(f"{product_name}发行公告")
            if title_is_split or title_is_inline:
                if "asset_full_name" not in found:
                    evidence = [_evidence(block.evidence_id, artifact_scope, document_name, page.physical_page, "公告标题", block.exact_text)]
                    if title_is_split and next_block:
                        evidence.append(_evidence(next_block.evidence_id, artifact_scope, document_name, page.physical_page, "公告标题", next_block.exact_text))
                    facts.append(
                        ExtractionFact(
                            fact_id=f"disclosed:asset-full-name:{block.evidence_id}",
                            field_id="asset_full_name",
                            entity_key=entity_key,
                            status=FactStatus.DISCLOSED,
                            value=product_name,
                            evidence=evidence,
                        )
                    )
                    found.add("asset_full_name")
            amount_candidates.extend(
                (page, block, next_block, match)
                for match in _ISSUE_TOTAL.finditer(normalized)
                if context[match.end() :].startswith(f"的{product_name}")
            )
            for match in _INITIAL_CUTOFF.finditer(block.exact_text):
                try:
                    value = date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
                except ValueError:
                    continue
                initial_cutoff_candidates.append((page, block, value))
    if len(initial_cutoff_candidates) == 1:
        page, block, value = initial_cutoff_candidates[0]
        facts.append(
            ExtractionFact(
                fact_id=f"disclosed:initial-cutoff-date:{block.evidence_id}",
                field_id="initial_cutoff_date",
                entity_key=entity_key,
                status=FactStatus.DISCLOSED,
                value=value,
                evidence=[_evidence(block.evidence_id, artifact_scope, document_name, page.physical_page, "初始起算日", block.exact_text)],
            )
        )
    if len(amount_candidates) == 1:
        page, block, next_block, match = amount_candidates[0]
        evidence = [_evidence(block.evidence_id, artifact_scope, document_name, page.physical_page, "发行规模/产品相邻文本", block.exact_text)]
        relation_end = match.end() + len(f"的{product_name}")
        if next_block and relation_end > len(re.sub(r"\s+", "", block.exact_text)):
            evidence.append(_evidence(next_block.evidence_id, artifact_scope, document_name, page.physical_page, "发行规模/产品相邻文本", next_block.exact_text))
        facts.append(
            ExtractionFact(
                fact_id=f"disclosed:issue-amount-all:{block.evidence_id}",
                field_id="issue_amount_all_tranches",
                entity_key=entity_key,
                status=FactStatus.DISCLOSED,
                value=format(Decimal(match.group(1).replace(",", "")) / Decimal("100000000"), "f"),
                evidence=evidence,
            )
        )
    return facts


def extract_issuance_result_ocr_facts(
    pages: list[PageContent], document_name: str, artifact_scope: str
) -> list[ExtractionFact]:
    """Extract complete tranche records from OCR of an issuance-result announcement."""
    if "簿记建档发行结果公告" not in document_name or not pages:
        return []
    product_name = Path(document_name).stem.removesuffix("簿记建档发行结果公告")
    first_page = next((page for page in pages if page.physical_page == 1 and page.ocr_requested), None)
    title = next((block for block in first_page.blocks if block.exact_text.strip()), None) if first_page else None
    if title is None or not re.sub(r"\s+", "", title.exact_text).startswith(f"{product_name}簿记建档发行结果公告"):
        return []
    records = []
    for page in pages:
        if not page.ocr_requested:
            continue
        values = {"security_code": [], "maturity_date": [], "tranche_issue_amount": []}
        level_candidates = []
        labels_seen = set()
        for index, block in enumerate(page.blocks):
            label = re.sub(r"\s+", "", block.exact_text)
            if label in {"证券代码", "预期到期日", "实际发行总额"}:
                labels_seen.add(label)
            if index + 1 == len(page.blocks):
                continue
            value_block = page.blocks[index + 1]
            value = re.sub(r"\s+", "", value_block.exact_text)
            if label == "证券代码" and _SECURITY_CODE.fullmatch(value):
                values["security_code"].append((value, block, value_block))
            elif label == "预期到期日" and (match := _EXPECTED_MATURITY.fullmatch(value)):
                try:
                    maturity = date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
                except ValueError:
                    continue
                values["maturity_date"].append((maturity, block, value_block))
            elif label == "实际发行总额" and (match := _AMOUNT_IN_TEN_THOUSANDS.fullmatch(value)):
                amount = format((Decimal(match.group(1).replace(",", "")) / Decimal("10000")).normalize(), "f")
                values["tranche_issue_amount"].append((amount, block, value_block))
            elif label == "证券名称":
                levels = [level for level in ("优先档", "次级档") if level in value]
                if len(levels) == 1:
                    level_candidates.append((levels[0], block, value_block, index))
        if labels_seen and not all(len(candidates) == 1 for candidates in values.values()):
            return []
        if labels_seen:
            code_label = values["security_code"][0][1]
            code_index = next(index for index, block in enumerate(page.blocks) if block is code_label)
            # ponytail: this OCR layout is one record/page; use table-cell geometry after the PP-Structure preflight is cleared.
            attached_levels = [candidate for candidate in level_candidates if 0 < code_index - candidate[3] <= 6]
            records.append(
                (page, {field_id: candidates[0] for field_id, candidates in values.items()}, attached_levels[0] if len(attached_levels) == 1 else None)
            )
    if len({values["security_code"][0] for _, values, _ in records}) != len(records):
        return []
    facts = []
    for page, values, level in records:
        code = values["security_code"][0]
        entity_key = f"security:{code}"
        for field_id, (value, label_block, value_block) in values.items():
            facts.append(
                ExtractionFact(
                    fact_id=f"disclosed:{field_id}:{value_block.evidence_id}",
                    field_id=field_id,
                    entity_key=entity_key,
                    status=FactStatus.DISCLOSED,
                    value=value,
                    evidence=[
                        _evidence(title.evidence_id, artifact_scope, document_name, 1, "公告标题", title.exact_text),
                        _evidence(label_block.evidence_id, artifact_scope, document_name, page.physical_page, "簿记建档结果公告/证券信息表", label_block.exact_text),
                        _evidence(value_block.evidence_id, artifact_scope, document_name, page.physical_page, "簿记建档结果公告/证券信息表", value_block.exact_text),
                    ],
                )
            )
        if level:
            value, label_block, value_block, _ = level
            facts.append(
                ExtractionFact(
                    fact_id=f"disclosed:tranche-level:{value_block.evidence_id}",
                    field_id="tranche_level",
                    entity_key=entity_key,
                    status=FactStatus.DISCLOSED,
                    value=value,
                    evidence=[
                        _evidence(title.evidence_id, artifact_scope, document_name, 1, "公告标题", title.exact_text),
                        _evidence(label_block.evidence_id, artifact_scope, document_name, page.physical_page, "簿记建档结果公告/证券信息表/证券名称", label_block.exact_text),
                        _evidence(value_block.evidence_id, artifact_scope, document_name, page.physical_page, "簿记建档结果公告/证券信息表/证券名称", value_block.exact_text),
                    ],
                )
            )
    return facts


def extract_prospectus_first_interest_payment_facts(
    pages: list[PageContent], document_name: str, association_facts: list[ExtractionFact], artifact_scope: str
) -> list[ExtractionFact]:
    """Project a uniquely disclosed first payment date through explicit tranche associations."""
    product_name = _product_name(document_name, "发行说明书")
    if not product_name:
        return []
    associations: dict[str, ExtractionFact] = {}
    associated_entities = set()
    for fact in association_facts:
        if fact.field_id != "tranche_level":
            continue
        source_products = {
            _product_name(item.document_name, "簿记建档发行结果公告")
            for item in fact.evidence
            if item.document_name.endswith("簿记建档发行结果公告.pdf")
        }
        if (
            fact.status is not FactStatus.DISCLOSED
            or fact.value not in {"优先档", "次级档"}
            or not fact.entity_key.startswith("security:")
            or source_products != {product_name}
            or fact.value in associations
            or fact.entity_key in associated_entities
        ):
            return []
        associations[fact.value] = fact
        associated_entities.add(fact.entity_key)
    candidates = []
    for page in pages:
        if page.ocr_requested:
            continue
        for block in page.blocks:
            if match := _FIRST_INTEREST_PAYMENT.search(block.exact_text):
                try:
                    candidates.append((page, block, date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()))
                except ValueError:
                    continue
    if len(candidates) != 1 or not associations:
        return []
    page, block, value = candidates[0]
    facts = []
    for level, association in sorted(associations.items()):
        facts.append(
            ExtractionFact(
                fact_id=f"disclosed:first-interest-payment:{association.entity_key}:{block.evidence_id}",
                field_id="first_interest_payment_date",
                entity_key=association.entity_key,
                status=FactStatus.DISCLOSED,
                value=value,
                evidence=[
                    _evidence(block.evidence_id, artifact_scope, document_name, page.physical_page, "发行要素/第一个支付日", block.exact_text),
                    *association.evidence,
                ],
            )
        )
    return facts


def extract_rating_report_facts(
    pages: list[PageContent], document_name: str, entity_key: str, artifact_scope: str
) -> list[ExtractionFact]:
    """Extract product-level facts from a native-text rating report."""
    if "信用评级报告" not in document_name:
        return []
    candidates = []
    for page in pages:
        if page.ocr_requested:
            continue
        for index, block in enumerate(page.blocks):
            section_blocks = page.blocks[max(0, index - 3) : index + 1]
            heading = next((item for item in reversed(section_blocks) if _INITIAL_POOL_SECTION.search(item.exact_text)), None)
            if not heading:
                continue
            candidates.extend((page, heading, block, match) for match in _INITIAL_POOL_BALANCE.finditer(block.exact_text))
    if len(candidates) != 1:
        return []
    page, heading, block, match = candidates[0]
    value = format((Decimal(match.group(1).replace(",", "")) * Decimal("10000")).normalize(), "f")
    evidence = [_evidence(heading.evidence_id, artifact_scope, document_name, page.physical_page, "资产池特征（于初始起算日）", heading.exact_text)]
    if heading is not block:
        evidence.append(_evidence(block.evidence_id, artifact_scope, document_name, page.physical_page, "资产池未偿本息费余额", block.exact_text))
    return [
        ExtractionFact(
            fact_id=f"disclosed:initial-pool-balance:{block.evidence_id}",
            field_id="initial_pool_outstanding_principal_interest_fees",
            entity_key=entity_key,
            status=FactStatus.DISCLOSED,
            value=value,
            evidence=evidence,
        )
    ]


def _product_name(document_name: str, suffix: str) -> str:
    stem = Path(document_name).stem
    if not stem.endswith(suffix):
        return ""
    return re.sub(r"\s+", "", stem.removesuffix(suffix))


def _evidence(evidence_id: str, artifact_scope: str, document_name: str, physical_page: int, locator: str, exact_text: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        artifact_scope=artifact_scope,
        document_name=document_name,
        physical_page=physical_page,
        locator=locator,
        exact_text=exact_text,
    )
