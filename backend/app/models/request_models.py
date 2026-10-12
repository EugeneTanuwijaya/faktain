from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Optional[str] = Field(None, max_length=20000, description="Teks berita atau caption gambar")
    url: Optional[str] = Field(None, max_length=2048, description="URL artikel yang ingin dianalisis")
    image_data_url: Optional[str] = Field(None, max_length=7_000_000, description="JPEG/PNG/WebP base64 data URL, maksimal 5 MiB")

    @model_validator(mode="after")
    def validate_modality(self):
        if self.text is not None:
            self.text = self.text.strip() or None
        if self.url is not None:
            self.url = self.url.strip() or None
        if self.image_data_url is not None and not self.image_data_url:
            raise ValueError("Gambar tidak boleh kosong")
        if self.url and (self.text or self.image_data_url):
            raise ValueError("Kirim satu input: teks, URL, atau gambar dengan caption opsional")
        if not (self.text or self.url or self.image_data_url):
            raise ValueError("Sertakan teks, URL, atau gambar")
        return self
