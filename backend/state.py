"""
CaseState — shared state that flows through the LangGraph ICR pipeline.

Every node reads from and writes to this TypedDict. LangGraph merges
partial updates returned by each node into the running state.
"""

from typing import Any, Optional
from typing_extensions import TypedDict


class DocumentInput(TypedDict):
    doc_type: str          # "application_form" | "government_id" | "policy_illustration"
    file_bytes_b64: str    # base64-encoded file content
    content_type: str      # MIME type
    filename: str


class Finding(TypedDict):
    rule_id: str
    severity: str          # "blocking" | "attention" | "advisory"
    description: str       # short human-readable title (e.g. "Question #14 answer missing")
    note: Optional[str]    # explanation of the issue and what action is needed
    source: str            # which document this came from
    triggered_by: str      # field or check that triggered this finding
    status: str            # "open" | "reviewed" | "waived"


class ReviewerAction(TypedDict):
    finding_rule_id: str
    action: str            # "confirm" | "override" | "waive"
    corrected_value: Optional[Any]
    reason: Optional[str]


class CaseState(TypedDict):
    case_id: str

    # Documents uploaded for this case
    documents: list[DocumentInput]

    # Identified product type (from classifier node)
    product_type: str      # "EAZY_HEALTH" | "IHP" | "UL_GAE" | "UL_NON_GAE" | "TRAD_GAE" | "TRAD_NON_GAE" | "UNKNOWN"

    # Merged extraction results keyed by doc_type
    extractions: dict

    # NB requirements evaluation (from nb_requirements.py)
    nb_requirements: dict

    # Cross-document validation results (from validator.py)
    validations: list[dict]

    # Per-document completeness scores (from scorer.py)
    completeness: dict

    # Overall case score and status
    case_score: int
    case_status: str       # "Ready for Review" | "Needs Attention" | "Incomplete / Refer Back"

    # Derived flags for routing
    needs_attention: bool

    # Separated validation lists for UI
    critical_flags: list[dict]
    warnings: list[dict]

    # Human-in-loop: findings presented to reviewer and their responses
    findings: list[Finding]
    reviewer_actions: list[ReviewerAction]

    # Any processing error
    error: Optional[str]
