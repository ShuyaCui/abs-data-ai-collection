from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

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
    pages: list[PageContent], document_name: str, entity_key: str
) -> list[ExtractionFact]:
    """Extract deterministic trustee-report facts from parser-owned text blocks."""
    report_date: ExtractionFact | None = None
    in_progress: RecoveryComponent | None = None
    completed: RecoveryComponent | None = None
    for page in pages:
        for block in page.blocks:
            if report_date is None and (match := _REPORT_DATE.search(block.exact_text)):
                value = f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
                report_date = ExtractionFact(
                    fact_id=f"disclosed:latest-report-date:{block.evidence_id}",
                    field_id="latest_report_date",
                    entity_key=entity_key,
                    status=FactStatus.DISCLOSED,
                    value=value,
                    evidence=[_evidence(block.evidence_id, document_name, page.physical_page, "封面/报告日期", block.exact_text)],
                )
            if in_progress is None and (match := _IN_PROGRESS_RECOVERY.search(block.exact_text)):
                in_progress = RecoveryComponent(
                    fact_id=f"disclosed:recovery-in-progress:{block.evidence_id}",
                    amount_cny=match.group(1).replace(",", ""),
                    evidence=_evidence(
                        block.evidence_id,
                        document_name,
                        page.physical_page,
                        "四、资产池表现情况/（三）资金池现金流流入/处置中/累计回收金额",
                        block.exact_text,
                    ),
                )
            if completed is None and (match := _COMPLETED_RECOVERY.search(block.exact_text)):
                completed = RecoveryComponent(
                    fact_id=f"disclosed:recovery-completed:{block.evidence_id}",
                    amount_cny=match.group(1).replace(",", ""),
                    evidence=_evidence(
                        block.evidence_id,
                        document_name,
                        page.physical_page,
                        "四、资产池表现情况/（三）资金池现金流流入/本期处置完毕/累计回收金额",
                        block.exact_text,
                    ),
                )
    facts = [fact for fact in [report_date] if fact is not None]
    if in_progress and completed:
        facts.append(derive_npl_recovery_cash(entity_key=entity_key, in_progress=in_progress, completed=completed))
    return facts


def _evidence(evidence_id: str, document_name: str, physical_page: int, locator: str, exact_text: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        document_name=document_name,
        physical_page=physical_page,
        locator=locator,
        exact_text=exact_text,
    )
