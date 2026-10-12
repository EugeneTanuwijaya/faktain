"""Server-owned evidence allowlist and conservative deterministic verdict gates."""
import re
from urllib.parse import urlsplit

from app.models.verification_models import ClaimResult, Evidence, ImageContext, VerificationResponse
from app.models.response_models import Indicator


def _space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def article_passages(content: str) -> list[dict]:
    parts = [paragraph[start:start + 2000] for paragraph in content.split('\n\n')
             for start in range(0, len(paragraph), 2000)]
    return [{'passage_id': f'P{i+1}', 'text': part} for i, part in enumerate(parts) if part.strip()]


def _records(value) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value) -> list[str]:
    return [item[:500] for item in value if isinstance(item, str) and item.strip()][:10] if isinstance(value, list) else []


def _evidence(items, sources: dict) -> list[Evidence]:
    accepted = []
    seen = set()
    for item in _records(items):
        source = sources.get(str(item.get("source_id", "")))
        quote = item.get("excerpt")
        if not source or not isinstance(quote, str) or not 20 <= len(_space(quote)) <= 2000 or len(quote) > 2000:
            continue
        if _space(quote) not in _space(source.get("content", "")):
            continue
        url = source.get("url", "")
        if urlsplit(url).scheme not in {"http", "https"} or not urlsplit(url).hostname:
            continue
        key = (source["id"], _space(quote))
        if key in seen:
            continue
        seen.add(key)
        accepted.append(Evidence(source_id=source["id"], title=source["title"], url=url, excerpt=quote))
    return accepted[:5]


def _aggregate(verdicts: list[str]) -> str:
    if not verdicts or all(v == "INSUFFICIENT_EVIDENCE" for v in verdicts):
        return "INSUFFICIENT_EVIDENCE"
    if "MISLEADING" in verdicts:
        return "MISLEADING"
    if all(v == "SUPPORTED" for v in verdicts):
        return "SUPPORTED"
    if all(v == "CONTRADICTED" for v in verdicts):
        return "CONTRADICTED"
    return "PARTIALLY_SUPPORTED" if any(v in {"SUPPORTED", "PARTIALLY_SUPPORTED"} for v in verdicts) else "INSUFFICIENT_EVIDENCE"


def normalize_result(raw: dict, claims: list[str], sources: list[dict], *, observation: dict | None = None,
                     matched_source_ids: set[str] | None = None, limitations: list[str] | None = None,
                     input_type: str = "text", orchestration: str = "native") -> VerificationResponse:
    raw = raw if isinstance(raw, dict) else {}
    indexed = {s["id"]: s for s in sources}
    matched = matched_source_ids or set()
    results = []
    judgments = _records(raw.get("claims"))
    for i, claim in enumerate(claims):
        matching = [j for j in judgments if j.get("claim_id") == f"C{i+1}"]
        judgment = matching[0] if len(matching) == 1 else {}
        support = _evidence(judgment.get("supporting_evidence"), indexed)
        contra = _evidence(judgment.get("contradicting_evidence"), indexed)
        limits = _strings(judgment.get("limitations"))
        context_value = judgment.get("context_issue")
        context_issue = isinstance(context_value, str) and context_value in {"TIME", "PLACE", "CAPTION"}
        visual_reference = bool(re.search(r"\b(foto|gambar|screenshot|photo|image|picture)\b", claim, re.I))
        if (context_issue or visual_reference) and observation is not None:
            original_count = len(support) + len(contra)
            support = [e for e in support if e.source_id in matched]
            contra = [e for e in contra if e.source_id in matched]
            if len(support) + len(contra) < original_count:
                limits.append("Evidence dari gambar sumber yang tidak cocok tidak dipakai untuk menetapkan konteks foto ini.")
        verdict = "INSUFFICIENT_EVIDENCE"
        if support and contra:
            verdict = "PARTIALLY_SUPPORTED"
        elif contra:
            verdict = "CONTRADICTED"
        elif support:
            verdict = "SUPPORTED"
        # Temporal text evidence alone does not prove an uploaded photo's identity.
        if (context_issue or visual_reference) and observation is not None:
            relevant_match = any(e.source_id in matched for e in support + contra)
            if not relevant_match:
                verdict = "INSUFFICIENT_EVIDENCE"
                limits.append("Belum ada kecocokan gambar sumber; tanggal/lokasi foto unggahan belum terverifikasi.")
        if (judgment.get("verdict") == "MISLEADING" and contra and context_issue
                and (observation is None or any(e.source_id in matched for e in contra))):
            verdict = "MISLEADING"
        requested = judgment.get("verdict")
        requested = requested if isinstance(requested, str) else ""
        if requested == "PARTIALLY_SUPPORTED" and support and verdict == "SUPPORTED":
            verdict = "PARTIALLY_SUPPORTED"
            limits.append("Sumber hanya mendukung sebagian detail klaim.")
        if requested not in {"SUPPORTED", "CONTRADICTED", "MISLEADING", "PARTIALLY_SUPPORTED"}:
            verdict = "INSUFFICIENT_EVIDENCE"
        if verdict == "INSUFFICIENT_EVIDENCE":
            limits.append("Bukti relevan yang dapat diperiksa belum cukup untuk menetapkan klaim.")
        reason = judgment.get("reasoning")
        if verdict == "INSUFFICIENT_EVIDENCE" and (requested != "INSUFFICIENT_EVIDENCE" or not isinstance(reason, str) or not reason.strip()):
            reason = "Klaim belum dapat dipastikan dari evidence yang diterima."
        results.append(ClaimResult(claim=claim, verdict=verdict,
                                  reasoning=reason[:1500] if isinstance(reason, str) and reason else "Periksa kutipan sumber yang disertakan.",
                                  supporting_evidence=support, contradicting_evidence=contra, limitations=list(dict.fromkeys(limits))))
    image_context = None
    if observation is not None:
        candidate = raw.get("image_context")
        candidate = candidate if isinstance(candidate, dict) else {}
        evidence = [e for e in _evidence(candidate.get("evidence"), indexed) if e.source_id in matched]
        verdict = candidate.get("verdict")
        if not evidence or not isinstance(verdict, str) or verdict not in {"VERIFIED_CONTEXT", "MISLEADING_CONTEXT"}:
            verdict = "INSUFFICIENT_EVIDENCE"
        image_limits = ["Pencocokan visual oleh model dapat keliru; tidak membuktikan keaslian, deepfake, atau tanggal pengambilan foto.",
                        "MVP tidak menjalankan pencarian gambar terbalik; gambar kandidat berasal dari artikel hasil pencarian teks."]
        if verdict == "INSUFFICIENT_EVIDENCE":
            image_limits.append("Asal gambar dan konteks waktu/lokasi belum dapat dipastikan dari sumber yang ditemukan.")
        reason = candidate.get("reasoning", "") if verdict != "INSUFFICIENT_EVIDENCE" else "Evidence belum cukup untuk memverifikasi konteks gambar."
        image_context = ImageContext(verdict=verdict, reasoning=reason if isinstance(reason, str) else "Periksa evidence konteks.",
                                     ocr_text=str(observation.get("ocr_text", ""))[:8000],
                                     visual_description=str(observation.get("visual_description", ""))[:2000],
                                     evidence=evidence, limitations=image_limits + _strings(observation.get("limitations")))
    overall = _aggregate([c.verdict for c in results])
    limits = list(limitations or [])
    if not results:
        limits.append("Tidak ada klaim faktual yang dapat diekstrak; tambahkan teks/caption yang lebih jelas.")
    if overall in {"INSUFFICIENT_EVIDENCE", "PARTIALLY_SUPPORTED"}:
        limits.append("Periksa hasil setiap klaim; tidak semua bagian input memiliki bukti yang cukup.")
    limits.append("Kutipan diperiksa terhadap teks sumber; relevansi dan kebenaran sumber tetap perlu ditinjau manusia.")
    allowed_signals = {"CLICKBAIT", "EMOTIONAL_LANGUAGE", "UNSOURCED_CLAIM", "INTERNAL_INCONSISTENCY", "ARTIFICIAL_URGENCY"}
    indicators = [Indicator(type=s["type"], description=s["description"][:500], severity=s["severity"])
                  for s in _records(raw.get("indicators")) if isinstance(s.get("type"), str) and s["type"] in allowed_signals
                  and isinstance(s.get("description"), str) and isinstance(s.get("severity"), str) and s["severity"] in {"low", "medium", "high"}][:5]
    return VerificationResponse(input_type=input_type, verdict=overall, indicators=indicators,
                                suggestion="Periksa sumber asli dan detail waktu/lokasi sebelum membagikan informasi.",
                                reasoning=f"{len(results)} klaim diperiksa. Kesimpulan mengikuti evidence per klaim.",
                                claims=results, image_context=image_context, limitations=list(dict.fromkeys(limits)),
                                orchestration=orchestration)
