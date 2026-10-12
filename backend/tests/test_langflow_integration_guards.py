"""Regression checks for shared deadlines and strict workflow integration."""
import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import settings
from app.models.langflow_models import validate_comparison
from app.models.request_models import AnalyzeRequest
from app.routers import analyze, news
from app.services import analysis_session_service as sessions, langflow_service, llm_service, verification_service
from app.services.evidence_service import normalize_result

CLAIM = 'Indonesia merdeka pada 17 Agustus 1945'
SOURCE = {'id': 'S1', 'title': 'Arsip', 'url': 'https://example.com', 'content': 'Indonesia merdeka pada 17 Agustus 1945.', 'image_url': None}


def judgment():
    return {'claims': [{'claim_id': 'C1', 'verdict': 'SUPPORTED', 'reasoning': 'Sumber mendukung tanggal.', 'supporting_evidence': [{'source_id': 'S1', 'excerpt': SOURCE['content']}], 'contradicting_evidence': [], 'limitations': []}], 'image_context': None, 'indicators': []}


async def test_url_ingestion_deducts_shared_deadline(monkeypatch):
    monkeypatch.setattr(settings, 'VERIFICATION_TIMEOUT', 1)
    async def scrape(url):
        await asyncio.sleep(0.03)
        return CLAIM
    verify = AsyncMock(return_value=normalize_result({}, [], [], input_type='url'))
    monkeypatch.setattr(analyze, 'scrape_article', scrape)
    monkeypatch.setattr(analyze, 'verify_content', verify)
    await analyze.analyze_content(AnalyzeRequest(url='https://example.com'), None)
    assert 0 < verify.call_args.kwargs['timeout'] < 0.98


async def test_news_ingestion_deducts_shared_deadline(monkeypatch):
    monkeypatch.setattr(settings, 'VERIFICATION_TIMEOUT', 1)
    item = SimpleNamespace(id='n1', title='Judul', source='Sumber', link='https://news.google.com')
    monkeypatch.setattr(news, 'get_news_by_id', AsyncMock(return_value=item))
    async def decode(link):
        await asyncio.sleep(0.03)
        return 'https://example.com/article'
    monkeypatch.setattr(news, 'decode_news_url', decode)
    monkeypatch.setattr(news, 'scrape_article', AsyncMock(return_value=SOURCE['content']))
    summarize = AsyncMock(return_value='Ringkasan artikel asli.')
    monkeypatch.setattr(news, 'summarize_article', summarize)
    await news.summarize_news_article('n1')
    assert 0 < summarize.call_args.kwargs['timeout'] < 0.98


@pytest.mark.parametrize('field', ['excerpt', 'reasoning'])
def test_whitespace_only_output_is_rejected(field):
    raw = judgment()
    if field == 'excerpt':
        raw['claims'][0]['supporting_evidence'][0]['excerpt'] = ' ' * 20
    else:
        raw['claims'][0]['reasoning'] = ' '
    with pytest.raises(ValueError):
        validate_comparison(raw, [CLAIM], [SOURCE])


async def test_summary_requires_reserved_model_stage(monkeypatch):
    monkeypatch.setattr(langflow_service, 'run_workflow', AsyncMock(return_value={'summary': 'Invented without model stage'}))
    with pytest.raises(langflow_service.LangflowOutputError):
        await langflow_service.summarize_with_langflow('Title', SOURCE['content'])


async def test_comparison_requires_reserved_model_stage(monkeypatch):
    async def flow(session, kind):
        await sessions.dispatch(session.id, 'ai-call', {'stage': 'extract', 'max_tokens': 1200})
        await sessions.dispatch(session.id, 'register', {'claims': [CLAIM]})
        session.sources.append(dict(SOURCE))
        return judgment()
    monkeypatch.setattr(verification_service, 'run_workflow', flow)
    monkeypatch.setattr(settings, 'LANGFLOW_NATIVE_FALLBACK', False)
    result = await verification_service.verify_content(CLAIM)
    assert result.verdict == 'INSUFFICIENT_EVIDENCE'
    assert any('tidak valid' in item for item in result.limitations)


async def test_failed_native_call_still_discloses_orchestration(monkeypatch):
    async def flow(session, kind):
        await sessions.dispatch(session.id, 'ai-call', {'stage': 'extract', 'max_tokens': 1200})
        await sessions.dispatch(session.id, 'register', {'claims': [CLAIM]})
        session.sources.append(dict(SOURCE))
        raise langflow_service.LangflowUnavailable('service unavailable')
    monkeypatch.setattr(verification_service, 'run_workflow', flow)
    monkeypatch.setattr(settings, 'LANGFLOW_NATIVE_FALLBACK', True)
    monkeypatch.setattr(verification_service, '_chat_completion', AsyncMock(side_effect=ValueError('failure')))
    result = await verification_service.verify_content(CLAIM)
    assert result.orchestration == 'native_fallback'
    assert any('Fallback' in item for item in result.limitations)


@pytest.mark.parametrize('body', [{'choices': None}, {'choices': [{'message': None}]}, {'choices': [{'message': {'content': {'claims': []}}}]}, {'choices': [{'message': {'content': '{"claims": []}'}, 'finish_reason': 'length'}]}])
async def test_native_malformed_or_truncated_response_is_bounded_failure(body, monkeypatch):
    monkeypatch.setattr(settings, 'LLM_API_KEY', 'unit-key')
    monkeypatch.setattr(settings, 'LLM_MAX_RETRIES', 1)
    original = httpx.AsyncClient
    with patch('httpx.AsyncClient', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)), **kw)):
        with pytest.raises(ValueError):
            await llm_service._chat_completion([{'role': 'user', 'content': 'Data'}], model_override='test/text', require_json=True, max_attempts=1)

async def test_ingestion_timeout_does_not_start_verification(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(settings, 'VERIFICATION_TIMEOUT', 0.01)
    async def scrape(url):
        await asyncio.sleep(1)
        return CLAIM
    verify = AsyncMock()
    monkeypatch.setattr(analyze, 'scrape_article', scrape)
    monkeypatch.setattr(analyze, 'verify_content', verify)
    with pytest.raises(HTTPException) as error:
        await analyze.analyze_content(AnalyzeRequest(url='https://example.com'), None)
    assert error.value.status_code == 422
    verify.assert_not_called()


async def test_workflow_timeout_preserves_registered_claims_without_native_call(monkeypatch):
    async def flow(session, kind):
        await sessions.dispatch(session.id, 'ai-call', {'stage': 'extract', 'max_tokens': 1200})
        await sessions.dispatch(session.id, 'register', {'claims': [CLAIM]})
        session.sources.append(dict(SOURCE))
        await asyncio.sleep(session.remaining_seconds)
        raise langflow_service.LangflowTimeout('expired')
    monkeypatch.setattr(verification_service, 'run_workflow', flow)
    direct = AsyncMock(side_effect=AssertionError('Expired deadline cannot fund fallback'))
    monkeypatch.setattr(verification_service, '_chat_completion', direct)
    result = await verification_service.verify_content(CLAIM, timeout=0.01)
    assert result.claims[0].claim == CLAIM
    assert result.orchestration == 'langflow'
    assert result.verdict == 'INSUFFICIENT_EVIDENCE'
    assert any('Waktu' in item for item in result.limitations)
    direct.assert_not_called()


@pytest.mark.parametrize('error_type, expected', [(langflow_service.LangflowTimeout, 504), (langflow_service.LangflowOutputError, 502), (langflow_service.LangflowUnavailable, 503)])
async def test_summary_failures_are_distinguished_without_upstream_details(monkeypatch, error_type, expected):
    from fastapi import HTTPException
    item = SimpleNamespace(id='n1', title='Judul', source='Sumber', link='https://news.google.com')
    monkeypatch.setattr(news, 'get_news_by_id', AsyncMock(return_value=item))
    monkeypatch.setattr(news, 'decode_news_url', AsyncMock(return_value='https://example.com/article'))
    monkeypatch.setattr(news, 'scrape_article', AsyncMock(return_value=SOURCE['content']))
    monkeypatch.setattr(news, 'summarize_article', AsyncMock(side_effect=error_type('credential-like upstream text')))
    with pytest.raises(HTTPException) as failure:
        await news.summarize_news_article('n1')
    assert failure.value.status_code == expected
    assert 'credential-like' not in failure.value.detail
