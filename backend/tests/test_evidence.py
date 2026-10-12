from app.services.evidence_service import normalize_result


SOURCE = {"id": "S1", "title": "Arsip banjir", "url": "https://example.com/archive",
          "content": "Foto ini diambil di Jakarta pada Januari 2020. Air mencapai dua meter."}


def assessment(verdict="SUPPORTED", supporting=None, contradicting=None):
    return {"claims": [{"claim_id": "C1", "verdict": verdict, "reasoning": "Bandingkan dengan arsip.",
                        "supporting_evidence": supporting or [],
                        "contradicting_evidence": contradicting or []}]}


def test_unknown_source_and_fabricated_quote_cannot_support_claim():
    raw = assessment(supporting=[{"source_id": "invented", "excerpt": "Foto ini"},
                                {"source_id": "S1", "excerpt": "Foto ini diambil tahun 2026"}])
    result = normalize_result(raw, ["Foto banjir Oktober 2026"], [SOURCE])
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert not result.claims[0].supporting_evidence
    assert result.claims[0].limitations
    assert "confidence_score" not in result.model_dump()


def test_support_requires_real_quote_and_server_owned_url():
    raw = assessment(supporting=[{"source_id": "S1", "excerpt": SOURCE["content"],
                                "url": "https://fabricated.example/fake"}])
    result = normalize_result(raw, ["Foto banjir Januari 2020"], [SOURCE])
    assert result.verdict == "SUPPORTED"
    assert result.claims[0].supporting_evidence[0].url == SOURCE["url"]


def test_model_cannot_say_supported_when_contradictions_exist():
    raw = assessment(supporting=[{"source_id": "S1", "excerpt": "Air mencapai dua meter."}],
                     contradicting=[{"source_id": "S1", "excerpt": "Foto ini diambil di Jakarta pada Januari 2020."}])
    assert normalize_result(raw, ["Banjir 2026 setinggi dua meter"], [SOURCE]).verdict == "PARTIALLY_SUPPORTED"


def test_image_date_conflict_without_image_match_is_insufficient():
    raw = assessment("MISLEADING", contradicting=[{"source_id": "S1", "excerpt": SOURCE["content"]}])
    raw["claims"][0]["context_issue"] = "TIME"
    raw["image_context"] = {"verdict": "MISLEADING_CONTEXT", "reasoning": "Foto lama.",
                            "evidence": [{"source_id": "S1", "excerpt": SOURCE["content"]}]}
    result = normalize_result(raw, ["Foto ini menunjukkan banjir hari ini"], [SOURCE],
                              observation={"ocr_text": "Banjir hari ini", "visual_description": "Jalan tergenang"})
    assert result.image_context.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.verdict == "INSUFFICIENT_EVIDENCE"


def test_image_context_requires_match_and_real_context_quote():
    raw = assessment("MISLEADING", contradicting=[{"source_id": "S1", "excerpt": SOURCE["content"]}])
    raw["claims"][0]["context_issue"] = "TIME"
    raw["image_context"] = {"verdict": "MISLEADING_CONTEXT", "reasoning": "Caption baru pada foto arsip.",
                            "evidence": [{"source_id": "S1", "excerpt": SOURCE["content"]}]}
    result = normalize_result(raw, ["Foto banjir hari ini"], [SOURCE], observation={}, matched_source_ids={"S1"})
    assert result.image_context.verdict == "MISLEADING_CONTEXT"
    assert result.verdict == "MISLEADING"
    assert result.image_context.limitations


def test_empty_claims_remain_insufficient():
    result = normalize_result({}, [], [])
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.limitations


def test_insufficient_retains_specific_evidence_gap_explanation():
    raw = assessment("INSUFFICIENT_EVIDENCE")
    raw["claims"][0]["reasoning"] = "Artikel mengonfirmasi lokasi, tetapi tidak menyebut jumlah korban."
    result = normalize_result(raw, ["Banjir Jakarta menyebabkan 300 korban"], [SOURCE])
    assert result.claims[0].reasoning == raw["claims"][0]["reasoning"]
    assert result.verdict == "INSUFFICIENT_EVIDENCE"


def test_rejected_support_does_not_retain_model_assertion_of_truth():
    raw = assessment("SUPPORTED")
    raw["claims"][0]["reasoning"] = "Klaim pasti benar."
    result = normalize_result(raw, ["Banjir Jakarta menyebabkan 300 korban"], [SOURCE])
    assert result.claims[0].reasoning == "Klaim belum dapat dipastikan dari evidence yang diterima."


def test_incomplete_claims_do_not_aggregate_to_supported():
    raw = assessment(supporting=[{"source_id": "S1", "excerpt": SOURCE["content"]}])
    result = normalize_result(raw, ["Foto tahun 2020", "Jumlah korban 300"], [SOURCE])
    assert result.verdict == "PARTIALLY_SUPPORTED"
    assert result.claims[1].verdict == "INSUFFICIENT_EVIDENCE"


def test_partial_support_is_not_promoted_to_full_support():
    raw = assessment("PARTIALLY_SUPPORTED", supporting=[{"source_id": "S1", "excerpt": SOURCE["content"]}])
    assert normalize_result(raw, ["Foto 2020 dan korban 300 orang"], [SOURCE]).verdict == "PARTIALLY_SUPPORTED"


def test_unknown_verdict_with_valid_quote_is_not_promoted():
    raw = assessment("definitely real", supporting=[{"source_id": "S1", "excerpt": SOURCE["content"]}])
    assert normalize_result(raw, ["Klaim pada sebuah gambar"], [SOURCE]).verdict == "INSUFFICIENT_EVIDENCE"


def test_image_provenance_claim_requires_match_even_if_model_omits_context_issue():
    raw = assessment(supporting=[{"source_id": "S1", "excerpt": SOURCE["content"]}])
    result = normalize_result(raw, ["Foto ini diambil pada Januari 2020"], [SOURCE], observation={})
    assert result.verdict == "INSUFFICIENT_EVIDENCE"


def test_reordered_comparison_must_follow_claim_ids_not_positions():
    raw = {"claims": [{"claim_id": "C2", "verdict": "SUPPORTED", "supporting_evidence": [{"source_id": "S1", "excerpt": SOURCE["content"]}]},
                       {"claim_id": "C1", "verdict": "INSUFFICIENT_EVIDENCE"}]}
    result = normalize_result(raw, ["Korban 300 orang", "Foto banjir Jakarta Januari 2020"], [SOURCE])
    assert result.claims[0].verdict == "INSUFFICIENT_EVIDENCE"
    assert result.claims[1].verdict == "SUPPORTED"


def test_malformed_judgment_fields_do_not_crash_or_support():
    raw = {"claims": [{"claim_id": "C1", "verdict": {}, "context_issue": [], "supporting_evidence": []}],
           "indicators": [{"type": [], "severity": {}, "description": "malformed"}],
           "image_context": {"verdict": {}, "evidence": []}}
    result = normalize_result(raw, ["Foto banjir pada Januari 2020"], [SOURCE], observation={})
    assert result.verdict == "INSUFFICIENT_EVIDENCE"


def test_unmatched_photo_evidence_cannot_contradict_matched_photo_context():
    other = {**SOURCE, "id": "S2", "url": "https://example.com/other", "content": "Foto berbeda diterbitkan pada tahun 2018 di kota Bandung."}
    raw = assessment(supporting=[{"source_id": "S1", "excerpt": SOURCE["content"]}],
                     contradicting=[{"source_id": "S2", "excerpt": other["content"]}])
    raw["claims"][0]["context_issue"] = "TIME"
    result = normalize_result(raw, ["Foto banjir Jakarta Januari 2020"], [SOURCE, other], observation={}, matched_source_ids={"S1"})
    assert result.verdict == "SUPPORTED"
    assert not result.claims[0].contradicting_evidence
    assert result.claims[0].limitations


def test_long_quote_is_not_silently_truncated_and_used_for_support():
    quote = "Konteks artikel. " * 160 + "Air banjir mencapai tepat dua meter."
    source = {**SOURCE, "content": quote}
    raw = assessment(supporting=[{"source_id": "S1", "excerpt": quote}])
    result = normalize_result(raw, ["Air banjir mencapai dua meter"], [source])
    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert not result.claims[0].supporting_evidence
