from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AgentFeedback(BaseModel):
    """Feedback model for agent decision quality and outcomes."""

    # Session/Trace Identification
    session_id: str = Field(..., description="Chat session identifier")
    trace_id: Optional[str] = Field(None, description="Specific agent trace to rate")

    # Decision Quality Ratings
    decision_accuracy: Optional[int] = Field(
        None, ge=1, le=5, description="Accuracy of agent decisions (1-5 scale)"
    )
    clinical_relevance: Optional[int] = Field(
        None, ge=1, le=5, description="Clinical relevance of analysis (1-5 scale)"
    )
    response_helpfulness: Optional[int] = Field(
        None, ge=1, le=5, description="Helpfulness of response (1-5 scale)"
    )

    # Specific Feedback Areas
    diagnosis_correctness: Optional[str] = Field(
        None, description="Was the diagnosis correct? (correct/incorrect/uncertain)"
    )
    triage_appropriateness: Optional[str] = Field(
        None, description="Was triage level appropriate? (appropriate/inappropriate/uncertain)"
    )
    report_quality: Optional[int] = Field(
        None, ge=1, le=5, description="Quality of generated report (1-5 scale)"
    )

    # User Corrections
    user_corrections: Optional[Dict[str, Any]] = Field(
        None, description="User corrections or additional context"
    )
    missed_findings: Optional[List[str]] = Field(
        None, description="Clinical findings that were missed"
    )
    incorrect_findings: Optional[List[str]] = Field(
        None, description="Findings that were incorrectly identified"
    )

    # Overall Assessment
    overall_satisfaction: Optional[int] = Field(
        None, ge=1, le=5, description="Overall user satisfaction (1-5 scale)"
    )
    would_recommend: Optional[bool] = Field(
        None, description="Would user recommend this to others?"
    )
    additional_comments: Optional[str] = Field(
        None, description="Additional user comments"
    )

    # Context Information
    actor_role: str = Field(..., description="User role (doctor/patient)")
    actor_id: str = Field(..., description="User identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "trace_id": "trace_456",
                "decision_accuracy": 4,
                "clinical_relevance": 5,
                "response_helpfulness": 4,
                "diagnosis_correctness": "correct",
                "triage_appropriateness": "appropriate",
                "report_quality": 5,
                "overall_satisfaction": 5,
                "would_recommend": True,
                "actor_role": "doctor",
                "actor_id": "doctor_123"
            }
        }


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    success: bool
    feedback_id: Optional[str] = None
    message: str
    feedback_analyzed: Optional[Dict[str, Any]] = None


class FeedbackSummary(BaseModel):
    """Summary of feedback for analytics."""

    total_feedback_count: int
    average_satisfaction: Optional[float]
    decision_accuracy_distribution: Dict[str, int]
    common_corrections: List[str]
    improvement_areas: List[str]
