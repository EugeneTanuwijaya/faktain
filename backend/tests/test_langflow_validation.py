import copy

import pytest


SOURCE = {"id": "S1", "title": "Arsip", "url": "https://example.com/archive",
          "content": "Proklamasi Indonesia berlangsung pada 17 Agustus 1945."}


def comparison():
    return {"claims": [{"claim_id": "C1", "verdict": "SUPPORTED", "reasoning": "Sumber menyebut tanggal tersebut.",
                        "context_issue": None, "supporting_evidence": [{"source_id": "S1", "excerpt": SOURCE["content"]}],
                        "contradicting_evidence": [], "limitations": []}], "image_context": None, "indicators": []}


def test_complete_comparison_preserves_real_article_evidence():
    from app.models.langflow_models import validate_comparison
    raw = validate_comparison(comparison(), ["Indonesia merdeka pada 17 Agustus 1945"], [SOURCE])
    assert raw["claims"][0]["supporting_evidence"][0]["excerpt"] == SOURCE["content"]


def test_backend_resolves_passage_id_to_original_quote_without_mutating_input():
    from app.models.langflow_models import validate_comparison
    from app.services.evidence_service import article_passages
    source = {**SOURCE, 'content': SOURCE['content'] + '\n\n' + 'Konteks lain. ' * 200}
    raw = comparison()
    raw['claims'][0]['supporting_evidence'] = [{'source_id': 'S1', 'passage_id': 'P1'}]
    result = validate_comparison(raw, ['Indonesia merdeka pada 17 Agustus 1945'], [source])
    assert result['claims'][0]['supporting_evidence'] == [{'source_id': 'S1', 'excerpt': SOURCE['content']}]
    assert raw['claims'][0]['supporting_evidence'][0]['passage_id'] == 'P1'
    passages = article_passages(source['content'])
    assert all(len(p['text']) <= 2000 and p['text'] in source['content'] for p in passages)
    assert len({p['passage_id'] for p in passages}) == len(passages)


@pytest.mark.parametrize('ref', [{'source_id': 'S99', 'passage_id': 'P1'}, {'source_id': 'S1', 'passage_id': 'P99'}, {'source_id': 'S1', 'passage_id': []}, {'source_id': 'S1', 'passage_id': 'P1', 'excerpt': 'Invented or altered text'}])
def test_fake_or_ambiguous_passage_reference_is_rejected(ref):
    from app.models.langflow_models import validate_comparison
    raw = comparison(); raw['claims'][0]['supporting_evidence'] = [ref]
    with pytest.raises(ValueError):
        validate_comparison(raw, ['Indonesia merdeka pada 17 Agustus 1945'], [SOURCE])


@pytest.mark.parametrize("mutation", ["missing_id", "duplicate_id", "unknown_id", "fake_source", "fake_quote", "invalid_enum", "coerced_type", "missing_field", "extra_credentials"])
def test_invalid_comparison_is_rejected_before_normalization(mutation):
    from app.models.langflow_models import validate_comparison
    raw = copy.deepcopy(comparison())
    claim = raw["claims"][0]
    if mutation == "missing_id": del claim["claim_id"]
    elif mutation == "duplicate_id": raw["claims"].append(copy.deepcopy(claim))
    elif mutation == "unknown_id": claim["claim_id"] = "C2"
    elif mutation == "fake_source": claim["supporting_evidence"][0]["source_id"] = "S99"
    elif mutation == "fake_quote": claim["supporting_evidence"][0]["excerpt"] = "Kutipan ini sama sekali tidak ada dalam artikel sumber."
    elif mutation == "invalid_enum": claim["verdict"] = "TRUE"
    elif mutation == "coerced_type": claim["reasoning"] = 123
    elif mutation == "missing_field": del claim["contradicting_evidence"]
    else: raw["credentials"] = "untrusted secret request"
    with pytest.raises(ValueError):
        validate_comparison(raw, ["Indonesia merdeka pada 17 Agustus 1945"], [SOURCE])
