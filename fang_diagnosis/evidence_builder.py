from __future__ import annotations

from typing import Any

from .types import Evidence, EvidenceStatus


def build_evidence(
    rule_id: str,
    status: EvidenceStatus,
    fields: list[str],
    formula: str,
    threshold: str,
    comparison: str,
    values: dict[str, Any],
    conclusion: str,
) -> Evidence:
    return Evidence(
        rule_id=rule_id,
        status=status,
        fields=fields,
        formula=formula,
        threshold=threshold,
        comparison=comparison,
        values=values,
        conclusion=conclusion,
    )

