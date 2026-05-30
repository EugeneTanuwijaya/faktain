from pydantic import BaseModel, Field
from typing import Optional


class AnalyzeRequest(BaseModel):
    text: Optional[str] = Field(None, description="Teks berita yang ingin dianalisis")
    url: Optional[str] = Field(None, description="URL artikel yang ingin dianalisis")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "text": "Presiden mengumumkan bahwa bumi itu datar menurut penelitian terbaru"
                },
                {
                    "url": "https://example.com/artikel-berita"
                }
            ]
        }
