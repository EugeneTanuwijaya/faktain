"""Strict Langflow outputs; final evidence provenance is owned by FastAPI."""
from typing import Literal
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.verification_models import Verdict, ImageVerdict
from app.services.evidence_service import _space, _records, article_passages


class StrictOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @field_validator("reasoning", "description", "summary", check_fields=False)
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Output text must not be blank")
        return value


class EvidenceReference(StrictOutput):
    source_id: str = Field(pattern=r"^S[1-5]$")
    excerpt: str = Field(min_length=20, max_length=2000)


class ClaimJudgment(StrictOutput):
    claim_id: str = Field(pattern=r"^C[1-3]$")
    verdict: Verdict
    reasoning: str = Field(min_length=1, max_length=3000)
    context_issue: Literal["TIME", "PLACE", "CAPTION"] | None = None
    supporting_evidence: list[EvidenceReference] = Field(max_length=5)
    contradicting_evidence: list[EvidenceReference] = Field(max_length=5)
    limitations: list[str] = Field(max_length=10)


class ImageJudgment(StrictOutput):
    verdict: ImageVerdict
    reasoning: str = Field(min_length=1, max_length=3000)
    evidence: list[EvidenceReference] = Field(max_length=5)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class StyleIndicator(StrictOutput):
    type: Literal["CLICKBAIT", "EMOTIONAL_LANGUAGE", "UNSOURCED_CLAIM", "INTERNAL_INCONSISTENCY", "ARTIFICIAL_URGENCY"]
    description: str = Field(min_length=1, max_length=500)
    severity: Literal["low", "medium", "high"]


class ComparisonOutput(StrictOutput):
    claims: list[ClaimJudgment] = Field(max_length=3)
    image_context: ImageJudgment | None
    indicators: list[StyleIndicator] = Field(max_length=5)


class SummaryOutput(StrictOutput):
    summary: str = Field(min_length=1, max_length=6000)


def validate_comparison(raw: dict, claims: list[str], sources: list[dict], *, is_image: bool = False) -> dict:
    raw = deepcopy(raw)
    indexed = {source['id']: source for source in sources}
    if isinstance(raw, dict):
        owners = _records(raw.get('claims')) + ([raw['image_context']] if isinstance(raw.get('image_context'), dict) else [])
        for owner in owners:
            for field in ('supporting_evidence', 'contradicting_evidence', 'evidence'):
                for ref in _records(owner.get(field)):
                    if set(ref) == {'source_id', 'passage_id'}:
                        if not isinstance(ref['source_id'], str) or not isinstance(ref['passage_id'], str):
                            raise ValueError('Invalid passage reference type')
                        source = indexed.get(ref['source_id'])
                        passages = {p['passage_id']: p['text'] for p in article_passages(source['content'])} if source else {}
                        if ref['passage_id'] not in passages:
                            raise ValueError('Unknown source or passage ID')
                        ref['excerpt'] = passages[ref.pop('passage_id')]
    result = ComparisonOutput.model_validate(raw)
    ids = [claim.claim_id for claim in result.claims]
    if len(ids) != len(set(ids)) or set(ids) != {f"C{i+1}" for i in range(len(claims))}:
        raise ValueError("Missing, duplicate or unknown claim ID")
    if is_image != (result.image_context is not None):
        raise ValueError("Image context does not match input modality")
    evidence = [item for claim in result.claims for item in claim.supporting_evidence + claim.contradicting_evidence]
    if result.image_context:
        evidence.extend(result.image_context.evidence)
    for item in evidence:
        source = indexed.get(item.source_id)
        if source is None or len(_space(item.excerpt)) < 20 or _space(item.excerpt) not in _space(source["content"]):
            raise ValueError("Evidence source or quote is not present in downloaded articles")
    return result.model_dump()
