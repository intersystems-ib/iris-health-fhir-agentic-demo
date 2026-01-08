"""
Pydantic schemas for structured outputs.

These schemas ensure that agent outputs match the structure
defined in ARCHITECTURE.md and can be persisted in the IRIS SQL schema.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class EvidenceItem(BaseModel):
    """
    Evidence fragment from clinical guidelines (RAG).
    Maps to CaseEvidences table.
    """
    guideline_id: str = Field(..., description="Logical guideline identifier (e.g., 'ckd_creatinine_demo')")
    chunk_id: str = Field(..., description="Reference to GuidelineChunks table")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Vector similarity score")
    excerpt: str = Field(..., description="Text excerpt shown to humans")


class RecommendationItem(BaseModel):
    """
    A specific follow-up action.
    Maps to CaseRecommendations table.
    """
    action_type: str = Field(
        ...,
        description="Type of action: repeat_test | med_review | monitor | imaging | referral | lifestyle"
    )
    action_text: str = Field(..., description="Human-readable action description")
    timeframe: Optional[str] = Field(None, description="When this should be done (e.g., '7–14 days', 'as soon as possible')")


class AssessmentSummary(BaseModel):
    """
    Clinical assessment summary.
    Maps to Cases table fields: risk_level, confidence, reasoning_summary.
    """
    risk_level: str = Field(
        ...,
        description="Risk classification: low | medium | medium-high | high"
    )
    confidence: str = Field(
        ...,
        description="Confidence level: low | medium | high"
    )
    reasoning_summary: str = Field(
        ...,
        description="Concise explanation of clinical reasoning (max 4000 chars)"
    )


class WorkflowMetadata(BaseModel):
    """
    Metadata about the AI workflow execution.
    Optional information for transparency and debugging.
    """
    orchestration_framework: str = Field(default="CrewAI", description="Framework used")
    crew_name: str = Field(default="renal_followup_crew", description="Name of the crew")
    model_provider: str = Field(default="OpenAI", description="LLM provider")
    model_name: str = Field(default="gpt-4.1-mini", description="Model used")
    guideline_version: str = Field(default="v1", description="Version of guidelines used")
    language: str = Field(default="en", description="Language of output")


class ClinicalRecommendationOutput(BaseModel):
    """
    Complete structured output from the Lab Follow-up Agent workflow.

    This is the JSON structure that CrewAI returns and that gets
    persisted into IRIS (Cases, CaseRecommendations, CaseEvidences tables).

    See ARCHITECTURE.md for the complete specification.
    """
    case_id: str = Field(..., description="Unique case identifier (UUID)")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO 8601 timestamp"
    )

    patient_ref: str = Field(..., description="FHIR patient reference (e.g., 'Patient/123')")
    trigger_observation_ref: str = Field(..., description="FHIR observation reference (e.g., 'Observation/987')")

    assessment: AssessmentSummary = Field(..., description="Clinical assessment summary")

    recommendations: List[RecommendationItem] = Field(
        ...,
        description="List of follow-up actions"
    )

    evidence: List[EvidenceItem] = Field(
        ...,
        description="Evidence fragments from guidelines (RAG)"
    )

    metadata: WorkflowMetadata = Field(
        default_factory=WorkflowMetadata,
        description="Workflow execution metadata"
    )


# ============================================================================
# Input schemas for tools
# ============================================================================

class PatientContext(BaseModel):
    """
    Patient clinical context retrieved from FHIR.
    Used internally by Context Agent.
    """
    patient_id: str
    recent_labs: List[dict] = Field(default_factory=list)
    active_medications: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    recent_vitals: Optional[dict] = None
