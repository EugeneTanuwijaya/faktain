import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.config import settings
from app.services import analysis_session_service as sessions
from app.routers.internal import router


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, 'LANGFLOW_SERVICE_KEY', 'unit-service-key', raising=False)
    app = FastAPI()
    app.include_router(router)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')


async def call(client, session, action, payload=None):
    if action == 'register':
        stage = 'observe' if session.input_type == 'image' else 'extract'
        if not session.stages.get(stage):
            await call(client, session, 'ai-call', {'stage': stage, 'max_tokens': 500})
    return await client.post(f'/internal/analyses/{session.id}/{action}', json=payload or {},
                             headers={'X-Faktain-Service-Key': 'unit-service-key'})


async def test_authenticated_strict_registration(client):
    session = sessions.create_session(text='untrusted instructions')
    try:
        response = await client.post(f'/internal/analyses/{session.id}/context', json={})
        assert response.status_code == 401
        assert (await call(client, session, 'register', {'claims': [123], 'limitations': []})).status_code == 422
        response = await call(client, session, 'register', {'claims': ['A factual claim'], 'limitations': []})
        assert response.json()['claim_ids'] == {'C1': 'A factual claim'}
        assert (await call(client, session, 'register', {'claims': []})).status_code == 409
        assert (await call(client, session, 'context', {'url': 'http://evil'})).status_code == 422
    finally:
        sessions.close_session(session.id)


async def test_race_safe_budget(client):
    session = sessions.create_session()
    try:
        responses = await asyncio.gather(*(call(client, session, 'ai-call', {'stage': 'extract', 'max_tokens': 1200}) for _ in range(4)))
        assert sorted(r.status_code for r in responses) == [200, 409, 409, 409]
        await call(client, session, 'register', {'claims': ['A factual claim']})
        assert (await call(client, session, 'ai-call', {'stage': 'compare', 'max_tokens': 2501})).status_code == 422
        assert (await call(client, session, 'ai-call', {'stage': 'compare', 'max_tokens': True})).status_code == 422
    finally:
        sessions.close_session(session.id)


async def test_search_bounds_stable_ids(client, monkeypatch):
    from app.services import search_service, verification_service
    search = AsyncMock(return_value=('', [{'url': f'https://example.org/{i}'} for i in range(10)]))
    async def retrieve(citation, source_id):
        return {'id': source_id, 'url': citation['url'], 'title': 'Title', 'content': 'Evidence article '*10, 'image_url': None}
    monkeypatch.setattr(search_service, 'search_messages', search)
    monkeypatch.setattr(verification_service, 'retrieve_source', retrieve)
    session = sessions.create_session()
    try:
        await call(client, session, 'register', {'claims': ['A factual claim']})
        payload = {'round': 0, 'queries': [{'claim_id': 'C1', 'query': 'support and refute'}]}
        first = await call(client, session, 'search', payload)
        assert [s['id'] for s in first.json()['sources']] == ['S1', 'S2', 'S3']
        payload['round'] = 1
        second = await call(client, session, 'search', payload)
        assert [s['id'] for s in second.json()['sources']] == ['S1', 'S2', 'S3', 'S4', 'S5']
        assert (await call(client, session, 'search', payload)).status_code == 409
        assert (await call(client, session, 'search', {'round': 2, 'queries': []})).status_code == 422
        assert search.await_count == 2
    finally:
        sessions.close_session(session.id)


async def test_image_registration_matches_and_deadline(client):
    session = sessions.create_session(input_type='image', image_data_url='normalized')
    try:
        assert (await call(client, session, 'register', {'claims': ['A factual claim']})).status_code == 422
        assert (await call(client, session, 'register', {'claims': [], 'observation': {'ocr_text': '', 'visual_description': '', 'limitations': ['OCR failed']}})).status_code == 200
        session.candidates = [{'source_id': 'S1', 'image_data_url': 'normalized'}]
        await call(client, session, 'ai-call', {'stage': 'match', 'max_tokens': 500})
        payload = {'matches': [{'source_id': 'S99', 'match': 'SAME_IMAGE', 'features': 'Distinctive matching details'}]}
        assert (await call(client, session, 'matches', payload)).status_code == 422
        payload['matches'][0]['source_id'] = 'S1'
        payload['matches'][0]['features'] = 'similar'
        assert (await call(client, session, 'matches', payload)).status_code == 422
        payload['matches'][0]['features'] = 'Distinctive matching details'
        assert (await call(client, session, 'matches', payload)).json()['matched_source_ids'] == ['S1']
        session.deadline = 0
        assert (await call(client, session, 'context')).status_code == 410
        assert sessions.get_session(session.id) is None
    finally:
        sessions.close_session(session.id)


async def test_summary_cannot_search_or_extract(client):
    session = sessions.create_session(input_type='summary', article_content='Original article')
    try:
        assert (await call(client, session, 'ai-call', {'stage': 'extract', 'max_tokens': 500})).status_code == 409
        assert (await call(client, session, 'search', {'round': 0, 'queries': []})).status_code == 409
        assert (await call(client, session, 'ai-call', {'stage': 'summarize', 'max_tokens': 500})).status_code == 200
    finally:
        sessions.close_session(session.id)


async def test_comparison_validation_and_repair_are_bounded(client):
    session = sessions.create_session(text='A factual claim')
    raw = {'claims': [{'claim_id': 'C1', 'verdict': 'SUPPORTED', 'reasoning': 'Artikel mendukung klaim.', 'supporting_evidence': [{'source_id': 'S1', 'excerpt': 'Evidence text invented by the model.'}], 'contradicting_evidence': [], 'limitations': []}], 'image_context': None, 'indicators': []}
    raw['claims'][0]['context_issue'] = None
    try:
        await call(client, session, 'register', {'claims': ['A factual claim']})
        session.sources = [{'id': 'S1', 'title': 'Article', 'url': 'https://example.org', 'content': 'Original article text that supports the claim.'}]
        assert (await call(client, session, 'ai-call', {'stage': 'compare_repair', 'max_tokens': 1700})).status_code == 409
        assert (await call(client, session, 'validate', {'result': raw})).status_code == 409
        await call(client, session, 'ai-call', {'stage': 'compare', 'max_tokens': 2500})
        response = await call(client, session, 'validate', {'result': raw})
        assert response.status_code == 200 and response.json()['valid'] is False
        assert 'result' not in response.json()
        assert (await call(client, session, 'validate', {'result': raw})).status_code == 409
        assert (await call(client, session, 'ai-call', {'stage': 'compare_repair', 'max_tokens': 1701})).status_code == 422
        assert (await call(client, session, 'ai-call', {'stage': 'compare_repair', 'max_tokens': 1700})).status_code == 200
        raw['claims'][0]['supporting_evidence'][0]['excerpt'] = session.sources[0]['content']
        response = await call(client, session, 'validate', {'result': raw})
        assert response.json()['valid'] is True and response.json()['result'] == raw
        assert session.output_tokens == 500 + 2500 + 1700
        assert (await call(client, session, 'ai-call', {'stage': 'compare_repair', 'max_tokens': 1700})).status_code == 409
        assert (await call(client, session, 'validate', {'result': raw})).status_code == 409
    finally:
        sessions.close_session(session.id)


async def test_repair_cannot_exceed_overall_token_budget(client, monkeypatch):
    monkeypatch.setattr(settings, 'VERIFICATION_MAX_OUTPUT_TOKENS', 4000)
    session = sessions.create_session(text='A factual claim')
    try:
        await call(client, session, 'register', {'claims': ['A factual claim']})
        await call(client, session, 'ai-call', {'stage': 'compare', 'max_tokens': 2500})
        assert (await call(client, session, 'validate', {'result': None})).json()['valid'] is False
        assert (await call(client, session, 'ai-call', {'stage': 'compare_repair', 'max_tokens': 1700})).status_code == 409
        assert session.output_tokens == 3000
    finally:
        sessions.close_session(session.id)

async def test_candidate_downloads_cached_and_bounded(client, monkeypatch):
    fetch = AsyncMock(return_value=(b'approved bytes', 'image/jpeg', 'https://source.example/image'))
    monkeypatch.setattr(sessions, 'safe_fetch', fetch)
    monkeypatch.setattr(sessions, 'bytes_to_image', lambda data, mime: 'normalized-metadata-free')
    session = sessions.create_session(input_type='image', image_data_url='normalized')
    session.sources = [{'id': f'S{i}', 'url': f'https://source.example/{i}', 'title': 'Title',
                        'content': 'Article', 'image_url': f'https://source.example/{i}.jpg'} for i in range(1, 6)]
    try:
        results = await asyncio.gather(*(call(client, session, 'candidates') for _ in range(3)))
        assert all(len(r.json()['candidates']) == 2 for r in results)
        assert fetch.await_count == 2
        assert results[0].json()['candidates'][0]['image_data_url'] == 'normalized-metadata-free'
        assert (await call(client, session, 'candidates', {'url': 'http://evil'})).status_code == 422
    finally:
        sessions.close_session(session.id)


async def test_failed_article_attempts_consume_budget(client, monkeypatch):
    from app.services import search_service, verification_service
    monkeypatch.setattr(search_service, 'search_messages', AsyncMock(return_value=('', [{'url': f'https://example.org/{i}'} for i in range(8)])))
    retrieve = AsyncMock(side_effect=ValueError('unsafe or unavailable'))
    monkeypatch.setattr(verification_service, 'retrieve_source', retrieve)
    session = sessions.create_session()
    try:
        await call(client, session, 'register', {'claims': ['A factual claim']})
        payload = {'round': 0, 'queries': [{'claim_id': 'C1', 'query': 'support and refute'}]}
        results = await asyncio.gather(call(client, session, 'search', payload), call(client, session, 'search', payload))
        assert sorted(r.status_code for r in results) == [200, 409]
        assert retrieve.await_count == 3
        payload['round'] = 1
        result = await call(client, session, 'search', payload)
        assert result.json()['sources'] == []
        assert retrieve.await_count == 5
        assert result.json()['limitations']
    finally:
        sessions.close_session(session.id)


async def test_shared_deadline_interrupts_network(client, monkeypatch):
    from app.services import search_service
    async def slow_search(messages):
        await asyncio.sleep(2)
        return '', []
    monkeypatch.setattr(search_service, 'search_messages', slow_search)
    session = sessions.create_session(timeout=0.08)
    await call(client, session, 'register', {'claims': ['A factual claim']})
    result = await call(client, session, 'search', {'round': 0, 'queries': [{'claim_id': 'C1', 'query': 'support'}]})
    assert result.status_code == 410
    assert sessions.get_session(session.id) is None
    assert session.claims == ['A factual claim']


async def test_stage_and_total_token_limits(client, monkeypatch):
    monkeypatch.setattr(settings, 'VERIFICATION_MAX_OUTPUT_TOKENS', 1200, raising=False)
    session = sessions.create_session()
    try:
        assert (await call(client, session, 'ai-call', {'stage': 'extract', 'max_tokens': 1200})).status_code == 200
        assert (await call(client, session, 'ai-call', {'stage': 'plan', 'max_tokens': 1})).status_code == 409
        assert (await call(client, session, 'ai-call', {'stage': 'observe', 'max_tokens': 1})).status_code == 409
    finally:
        sessions.close_session(session.id)

async def test_phase_guards_and_matches_replay(client):
    session = sessions.create_session(input_type='image', image_data_url='normalized')
    try:
        assert (await call(client, session, 'ai-call', {'stage': 'compare', 'max_tokens': 100})).status_code == 409
        assert (await call(client, session, 'ai-call', {'stage': 'match', 'max_tokens': 100})).status_code == 409
        await call(client, session, 'register', {'claims': ['A factual claim'], 'observation': {'ocr_text': '', 'visual_description': ''}})
        assert (await call(client, session, 'ai-call', {'stage': 'observe', 'max_tokens': 100})).status_code == 409
        session.candidates = [{'source_id': 'S1', 'image_data_url': 'normalized'}, {'source_id': 'S2', 'image_data_url': 'normalized'}]
        await call(client, session, 'ai-call', {'stage': 'match', 'max_tokens': 500})
        await call(client, session, 'ai-call', {'stage': 'match', 'max_tokens': 500})
        assert (await call(client, session, 'matches', {'matches': []})).status_code == 422
        payload = {'matches': [{'source_id': s, 'match': 'DIFFERENT', 'features': 'Similar subject only'} for s in ('S1', 'S2')]}
        responses = await asyncio.gather(call(client, session, 'matches', payload), call(client, session, 'matches', payload))
        assert sorted(r.status_code for r in responses) == [200, 409]
        assert session.matched_source_ids == set()
    finally:
        sessions.close_session(session.id)


async def test_fallback_private_reservation_and_global_caps(client, monkeypatch):
    session = sessions.create_session()
    session.claims = ['A factual claim']
    session.registered = True
    session.sources = [{'id': 'S1', 'title': 'Title', 'url': 'https://example.org', 'content': 'Evidence'}]
    try:
        session.stages['compare'] = 1
        session.output_tokens = 2500
        results = await asyncio.gather(sessions.reserve_fallback(session), sessions.reserve_fallback(session), return_exceptions=True)
        assert len([r for r in results if isinstance(r, dict)]) == 1
        assert session.output_tokens == 5000
        assert (await call(client, session, 'ai-call', {'stage': 'native_fallback', 'max_tokens': 1})).status_code == 422
        session.stages = {'other': 8}
        session.output_tokens = 0
        assert (await call(client, session, 'ai-call', {'stage': 'plan', 'max_tokens': 1})).status_code == 409
        session.deadline = 0
        with pytest.raises(Exception) as failure:
            await sessions.reserve_fallback(session)
        assert failure.value.status_code == 410
    finally:
        sessions.close_session(session.id)


async def test_callback_payload_cap_and_duplicate_claims(client):
    session = sessions.create_session()
    try:
        assert (await call(client, session, 'register', {'claims': ['A factual claim', 'A factual claim']})).status_code == 422
        response = await client.post(f'/internal/analyses/{session.id}/context',
                                     content=' ' * 16385,
                                     headers={'X-Faktain-Service-Key': 'unit-service-key'})
        assert response.status_code == 413
    finally:
        sessions.close_session(session.id)

async def test_input_registration_and_match_reservations_required(client):
    text = sessions.create_session()
    image = sessions.create_session(input_type='image', image_data_url='normalized')
    try:
        with pytest.raises(Exception) as error:
            await sessions.dispatch(text.id, 'register', {'claims': ['A factual claim']})
        assert error.value.status_code == 409
        assert (await call(client, image, 'ai-call', {'stage': 'extract', 'max_tokens': 500})).status_code == 409
        with pytest.raises(Exception) as error:
            await sessions.dispatch(image.id, 'register', {'claims': [], 'observation': {'ocr_text': '', 'visual_description': ''}})
        assert error.value.status_code == 409
        await call(client, image, 'register', {'claims': [], 'observation': {'ocr_text': '', 'visual_description': ''}})
        image.candidates = [{'source_id': 'S1', 'image_data_url': 'normalized'}]
        payload = {'matches': [{'source_id': 'S1', 'match': 'DIFFERENT', 'features': 'Similar subject'}]}
        assert (await call(client, image, 'matches', payload)).status_code == 409
        await call(client, image, 'ai-call', {'stage': 'match', 'max_tokens': 500})
        assert (await call(client, image, 'matches', payload)).status_code == 200
    finally:
        sessions.close_session(text.id)
        sessions.close_session(image.id)
