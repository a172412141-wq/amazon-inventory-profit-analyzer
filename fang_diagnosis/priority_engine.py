from __future__ import annotations

from dataclasses import replace

from .types import RelationshipFinding, ValidationResult


PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def prioritize_findings(findings: list[RelationshipFinding], validation: ValidationResult) -> list[RelationshipFinding]:
    result: list[RelationshipFinding] = []
    for finding in findings:
        severity = finding.severity
        if finding.code in {"FANG_REL_010", "FANG_REL_009", "FANG_CORE_001"}:
            severity = "P0"
        if finding.code == "FANG_REL_008":
            severity = "P3"
        result.append(replace(finding, severity=severity))
    return sorted(result, key=lambda item: (PRIORITY_ORDER[item.severity], 0 if item.status == "confirmed" else 1, item.code))

