"""Version 2 API contract: evidence, never an uncalibrated confidence score."""
from typing import Literal

from pydantic import BaseModel, Field
from app.models.response_models import Indicator

Verdict = Literal["SUPPORTED", "CONTRADICTED", "MISLEADING", "PARTIALLY_SUPPORTED", "INSUFFICIENT_EVIDENCE"]
ImageVerdict = Literal["VERIFIED_CONTEXT", "MISLEADING_CONTEXT", "INSUFFICIENT_EVIDENCE"]


class Evidence(BaseModel):
    source_id: str
    title: str
    url: str
    excerpt: str


class ClaimResult(BaseModel):
    claim: str
    verdict: Verdict
    reasoning: str
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    contradicting_evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ImageContext(BaseModel):
    verdict: ImageVerdict = "INSUFFICIENT_EVIDENCE"
    reasoning: str
    ocr_text: str = ""
    visual_description: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class VerificationResponse(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    input_type: Literal["text", "url", "image"] = "text"
    verdict: Verdict
    reasoning: str
    claims: list[ClaimResult] = Field(default_factory=list)
    image_context: ImageContext | None = None
    limitations: list[str] = Field(default_factory=list)
    analyzed_text: str = ""
    orchestration: Literal["native", "langflow", "native_fallback"] = "native"
    indicators: list[Indicator] = Field(default_factory=list)
    suggestion: str = ""
