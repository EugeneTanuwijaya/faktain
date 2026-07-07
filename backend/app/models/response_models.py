from pydantic import BaseModel, Field
from typing import List, Optional


class Indicator(BaseModel):
    type: str = Field(..., description="Jenis indikator hoaks")
    description: str = Field(..., description="Penjelasan indikator")
    severity: str = Field(..., description="Tingkat keparahan: low, medium, high")


class VerifiedClaim(BaseModel):
    claim: str = Field(..., description="Klaim yang diekstrak dari teks")
    status: str = Field(..., description="TERKONFIRMASI | DIBANTAH | TIDAK DAPAT DIVERIFIKASI")
    explanation: str = Field(..., description="Penjelasan hasil verifikasi")
    is_core: bool = Field(
        True,
        description=(
            "True jika klaim ini benar-benar dinyatakan user (inti). False jika "
            "klaim pendukung/konteks tambahan dari hasil pencarian."
        ),
    )


class Source(BaseModel):
    title: str = Field(..., description="Judul sumber")
    url: str = Field(..., description="URL sumber")
    credibility: str = Field(..., description="TERPERCAYA | NETRAL | MERAGUKAN")


class AnalysisResponse(BaseModel):
    confidence_score: int = Field(..., ge=0, le=100, description="Skor kepercayaan 0-100")
    verdict: str = Field(..., description="KREDIBEL | PERLU DICEK | KEMUNGKINAN HOAKS")
    reasoning: str = Field(..., description="Penjelasan singkat 2-3 kalimat")
    indicators: List[Indicator] = Field(default_factory=list)
    verified_claims: List[VerifiedClaim] = Field(default_factory=list)
    sources_found: List[Source] = Field(default_factory=list)
    suggestion: str = Field("", description="Saran verifikasi lebih lanjut")
    analyzed_text: Optional[str] = Field(None, description="Teks yang dianalisis (snippet)")


class NewsItem(BaseModel):
    id: str
    title: str
    link: str
    source: str
    published: str
    summary: Optional[str] = None
    image_url: Optional[str] = None


class NewsFeedResponse(BaseModel):
    articles: List[NewsItem]
    last_updated: str


class NewsSummaryResponse(BaseModel):
    id: str = Field(..., description="ID berita")
    title: str = Field(..., description="Judul berita")
    source: str = Field("", description="Sumber/media berita")
    original_url: str = Field(..., description="URL artikel asli (hasil decode)")
    summary: str = Field(..., description="Ringkasan AI dari isi artikel")


class ErrorResponse(BaseModel):
    detail: str
