from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypedDict


EvidenceStatus = Literal["confirmed", "probable", "hypothesis", "unknown"]
Priority = Literal["P0", "P1", "P2", "P3"]
Confidence = Literal["high", "medium", "low"]


class DiagnosisInput(TypedDict, total=False):
    metadata: dict[str, Any]
    scope: dict[str, Any]
    sales: dict[str, Any]
    advertising: dict[str, Any]
    profitability: dict[str, Any]
    inventory: dict[str, Any]
    skuRoles: dict[str, Any]
    skuDetails: list[dict[str, Any]]
    sourcePresence: dict[str, bool]


@dataclass(frozen=True)
class Evidence:
    rule_id: str
    status: EvidenceStatus
    fields: list[str]
    formula: str
    threshold: str
    comparison: str
    values: dict[str, Any]
    conclusion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "status": self.status,
            "fields": self.fields,
            "formula": self.formula,
            "threshold": self.threshold,
            "comparison": self.comparison,
            "values": self.values,
            "conclusion": self.conclusion,
        }


@dataclass(frozen=True)
class DataIssue:
    code: str
    severity: Literal["error", "warning", "info"]
    field: str
    message: str
    expected: float | None = None
    actual: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _clean(asdict(self))


@dataclass
class ValidationResult:
    is_valid: bool
    confidence: Confidence
    issues: list[DataIssue] = field(default_factory=list)
    blocked_fields: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "isValid": self.is_valid,
            "confidence": self.confidence,
            "issues": [issue.to_dict() for issue in self.issues],
            "blockedFields": sorted(self.blocked_fields),
        }


@dataclass(frozen=True)
class RelationshipFinding:
    code: str
    title: str
    severity: Priority
    status: EvidenceStatus
    description: str
    evidence: list[Evidence]
    business_impact: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
            "evidence": [item.to_dict() for item in self.evidence],
            "businessImpact": self.business_impact,
        }


@dataclass(frozen=True)
class ActionItem:
    priority: Priority
    target_type: Literal["sku", "parent", "productLine", "advertising", "inventory", "data"]
    target_id: str | None
    problem: str
    evidence: list[Evidence]
    business_impact: str
    action: str
    owner: str | None
    start_time: str
    deadline: str
    observation_period_days: int
    success_criteria: list[str]
    failure_plan: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "targetType": self.target_type,
            "targetId": self.target_id,
            "problem": self.problem,
            "evidence": [item.to_dict() for item in self.evidence],
            "businessImpact": self.business_impact,
            "action": self.action,
            "owner": self.owner,
            "startTime": self.start_time,
            "deadline": self.deadline,
            "observationPeriodDays": self.observation_period_days,
            "successCriteria": self.success_criteria,
            "failurePlan": self.failure_plan,
        }


@dataclass(frozen=True)
class RuleRecord:
    rule_id: str
    name: str
    version: str
    status: Literal["stable", "provisional", "experimental"]
    source: str
    description: str
    input_fields: list[str]
    output_type: str
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "source": self.source,
            "description": self.description,
            "inputFields": self.input_fields,
            "outputType": self.output_type,
            "enabled": self.enabled,
        }


@dataclass
class DiagnosisReport:
    model_version: str
    executive_conclusion: str
    business_stage: dict[str, Any]
    confirmed_facts: list[str]
    core_contradiction: dict[str, str]
    priorities: list[dict[str, Any]]
    relationship_findings: list[RelationshipFinding]
    sku_structure: dict[str, Any]
    inventory_diagnosis: dict[str, Any]
    advertising_diagnosis: dict[str, Any]
    profitability_diagnosis: dict[str, Any]
    data_quality: ValidationResult
    action_plan: list[ActionItem]
    missing_data: list[str]
    final_one_sentence_conclusion: str
    rule_execution: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return _clean(
            {
                "modelVersion": self.model_version,
                "executiveConclusion": self.executive_conclusion,
                "businessStage": self.business_stage,
                "confirmedFacts": self.confirmed_facts,
                "coreContradiction": self.core_contradiction,
                "priorities": self.priorities,
                "relationshipFindings": [item.to_dict() for item in self.relationship_findings],
                "skuStructure": self.sku_structure,
                "inventoryDiagnosis": self.inventory_diagnosis,
                "advertisingDiagnosis": self.advertising_diagnosis,
                "profitabilityDiagnosis": self.profitability_diagnosis,
                "dataQuality": self.data_quality.to_dict(),
                "actionPlan": [item.to_dict() for item in self.action_plan],
                "missingData": self.missing_data,
                "finalOneSentenceConclusion": self.final_one_sentence_conclusion,
                "ruleExecution": self.rule_execution,
            }
        )


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, float) and (value != value or value in {float("inf"), float("-inf")}):
        return None
    return value

