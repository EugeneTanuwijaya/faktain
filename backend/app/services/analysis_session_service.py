"""Ephemeral, service-authenticated evidence boundary for Langflow workflows."""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings
from app.services.image_service import bytes_to_image
from app.services.url_safety import safe_fetch
from app.services.evidence_service import article_passages


class StrictPayload(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')


class Empty(StrictPayload):
    pass


class Validate(StrictPayload):
    result: dict | None


class Observation(StrictPayload):
    ocr_text: str = Field(max_length=8000)
    visual_description: str = Field(max_length=2000)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class Register(StrictPayload):
    claims: list[str] = Field(max_length=3)
    observation: Observation | None = None
    limitations: list[str] = Field(default_factory=list, max_length=10)


class Query(StrictPayload):
    claim_id: str
    query: str = Field(min_length=1, max_length=2000)


class Search(StrictPayload):
    round: int = Field(ge=0, le=1)
    queries: list[Query] = Field(max_length=3)


STAGE_TOKENS = {'extract': 1200, 'observe': 1800, 'plan': 900, 'adequacy': 1600,
                'match': 500, 'compare': 2500, 'compare_repair': 1700, 'summarize': 500}


class AICall(StrictPayload):
    stage: Literal['extract', 'observe', 'plan', 'adequacy', 'match', 'compare', 'compare_repair', 'summarize']
    max_tokens: int = Field(ge=1)


class Match(StrictPayload):
    source_id: str
    match: Literal['SAME_IMAGE', 'DIFFERENT', 'UNCERTAIN']
    features: str = Field(max_length=2000)


class Matches(StrictPayload):
    matches: list[Match] = Field(max_length=2)


@dataclass
class AnalysisSession:
    text: str
    input_type: str
    image_data_url: str | None
    title: str
    article_content: str
    deadline: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    claims: list[str] = field(default_factory=list)
    observation: dict | None = None
    sources: list[dict] = field(default_factory=list)
    matched_source_ids: set[str] = field(default_factory=set)
    limitations: list[str] = field(default_factory=list)
    candidates: list[dict] | None = None
    registered: bool = False
    rounds: int = 0
    article_attempts: int = 0
    candidate_attempts: int = 0
    attempted_urls: set[str] = field(default_factory=set)
    stages: dict[str, int] = field(default_factory=dict)
    output_tokens: int = 0
    matches_confirmed: bool = False
    comparison_invalid: bool = False
    comparison_checks: int = 0
    reference_date: str = field(default_factory=lambda: datetime.now(timezone(timedelta(hours=7))).date().isoformat())

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def envelope(self) -> dict:
        return {'claims': list(self.claims), 'claim_ids': {f'C{i+1}': claim for i, claim in enumerate(self.claims)},
                'sources': [{k: s[k] for k in ('id', 'title', 'url')} | {'content': article_passages(s['content'])} for s in self.sources],
                'image_observation': self.observation, 'original_input': self.text[:12000],
                'matched_source_ids': sorted(self.matched_source_ids), 'limitations': list(self.limitations),
                'reference_date': self.reference_date, 'reference_timezone': 'Asia/Jakarta',
                'remaining_seconds': self.remaining_seconds}


_sessions: dict[str, AnalysisSession] = {}


def create_session(text='', input_type='text', image_data_url=None, title='', article_content='', timeout=None) -> AnalysisSession:
    # Lazy expiry is sufficient because every request closes its session in finally.
    for session_id, session in list(_sessions.items()):
        if not session.remaining_seconds:
            close_session(session_id)
    session = AnalysisSession(text, input_type, image_data_url, title, article_content,
                              time.monotonic() + (settings.VERIFICATION_TIMEOUT if timeout is None else timeout))
    if len(text) > 12000:
        session.limitations.append('Input dibatasi pada 12.000 karakter untuk ekstraksi klaim.')
    _sessions[session.id] = session
    return session


def close_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def get_session(session_id: str) -> AnalysisSession | None:
    session = _sessions.get(session_id)
    if session and not session.remaining_seconds:
        close_session(session_id)
        return None
    return session


def reject(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


async def _search(session: AnalysisSession, payload: Search):
    from app.services.search_service import search_messages, SearchBlocked
    from app.services.verification_service import retrieve_source

    if not session.registered or payload.round != session.rounds or session.rounds >= 2:
        reject(409, 'Search round unavailable')
    ids = [q.claim_id for q in payload.queries]
    if len(ids) != len(set(ids)) or any(i not in session.envelope()['claim_ids'] for i in ids):
        reject(422, 'Unregistered or repeated claim ID')
    if any(not q.query.strip() for q in payload.queries):
        reject(422, 'Empty search query')
    session.rounds += 1
    if not settings.LLM_WEB_SEARCH:
        session.limitations.append('Pencarian web dinonaktifkan; ingatan model bukan evidence.')
        return
    citations = {}
    for query in payload.queries:
        try:
            _, found = await search_messages([{'role': 'user', 'content': query.query}])
            for citation in found:
                if isinstance(citation, dict) and isinstance(citation.get('url'), str):
                    citations.setdefault(citation['url'], citation)
        except SearchBlocked as exc:
            session.limitations.append(str(exc))
            break
        except (ValueError, OSError, httpx.HTTPError):
            session.limitations.append('Layanan pencarian evidence gagal; sebagian bukti belum tersedia.')
    # Attempts, including failures, consume slots: retries cannot expand network cost.
    round_cap = 3 if payload.round == 0 else 5
    for url, citation in citations.items():
        if session.article_attempts >= round_cap:
            break
        if url in session.attempted_urls:
            continue
        session.attempted_urls.add(url)
        session.article_attempts += 1
        source_id = f'S{session.article_attempts}'
        try:
            source = await retrieve_source(citation, source_id)
            if not any(s['url'] == source['url'] for s in session.sources):
                session.sources.append(source)
        except (ValueError, OSError, httpx.HTTPError):
            session.limitations.append('Sebagian artikel sumber tidak dapat diambil; artikel tersebut bukan evidence.')
    if not session.sources:
        session.limitations.append('Tidak ada artikel evidence yang berhasil diambil.')


async def _candidates(session: AnalysisSession):
    if session.input_type != 'image':
        reject(409, 'Candidate images require image input')
    if session.candidates is not None:
        return
    session.candidates = []
    for source in session.sources:
        if session.candidate_attempts >= 2:
            break
        if not source.get('image_url'):
            continue
        session.candidate_attempts += 1
        try:
            data, mime, _ = await safe_fetch(source['image_url'], max_bytes=5 * 1024 * 1024,
                                           accepted_types=('image/jpeg', 'image/png', 'image/webp'))
            candidate = await asyncio.to_thread(bytes_to_image, data, mime)
            session.candidates.append({'source_id': source['id'], 'image_data_url': candidate})
        except (ValueError, OSError, httpx.HTTPError):
            session.limitations.append('Gambar kandidat sumber tidak dapat diambil dengan aman.')


async def dispatch(session_id: str, action: str, raw: dict) -> dict:
    session = get_session(session_id)
    if session is None:
        reject(410, 'Analysis session expired or unavailable')
    models = {'context': Empty, 'register': Register, 'search': Search, 'candidates': Empty,
              'matches': Matches, 'ai-call': AICall, 'validate': Validate}
    if action not in models:
        reject(404, 'Unknown analysis action')
    try:
        payload = models[action].model_validate(raw)
    except ValidationError:
        reject(422, 'Invalid analysis callback schema')
    async with session.lock:
        if get_session(session_id) is not session:
            reject(410, 'Analysis session expired or unavailable')
        if session.input_type == 'summary' and action not in ('context', 'ai-call'):
            reject(409, 'Summary workflow cannot request evidence')
        try:
            async with asyncio.timeout(session.remaining_seconds):
                if action == 'context':
                    return {**session.envelope(), 'text': session.text[:12000], 'input_type': session.input_type,
                            'image_data_url': session.image_data_url, 'title': session.title,
                            'article_content': session.article_content}
                if action == 'register':
                    if session.registered:
                        reject(409, 'Claims already registered')
                    required_stage = 'observe' if session.input_type == 'image' else 'extract'
                    if not session.stages.get(required_stage):
                        reject(409, 'Input AI stage has not been reserved')
                    claims = [c.strip() for c in payload.claims]
                    if any(not 10 <= len(c) <= 600 for c in claims) or len(claims) != len(set(claims)):
                        reject(422, 'Invalid or duplicate claims')
                    if session.input_type == 'image' and payload.observation is None:
                        reject(422, 'Image observation required')
                    if session.input_type != 'image' and payload.observation is not None:
                        reject(422, 'Unexpected image observation')
                    session.claims = claims
                    session.observation = payload.observation.model_dump() if payload.observation else None
                    session.limitations.extend(payload.limitations)
                    if payload.observation:
                        session.limitations.extend(payload.observation.limitations)
                    session.registered = True
                elif action == 'ai-call':
                    stage = payload.stage
                    if (session.input_type == 'summary') != (stage == 'summarize'):
                        reject(409, 'Stage not permitted for workflow')
                    if stage in ('observe', 'match') and session.input_type != 'image':
                        reject(409, 'Vision stage requires image input')
                    if stage == 'extract' and session.input_type == 'image':
                        reject(409, 'Image extraction requires vision observation')
                    if stage in ('extract', 'observe') and session.registered:
                        reject(409, 'Input already registered')
                    if stage in ('plan', 'adequacy', 'compare', 'compare_repair') and not (session.registered and session.claims):
                        reject(409, 'Registered claims required')
                    if stage == 'compare_repair' and not session.comparison_invalid:
                        reject(409, 'Repair requires a rejected comparison')
                    if stage == 'match' and not session.candidates:
                        reject(409, 'Approved candidates required')
                    if payload.max_tokens > STAGE_TOKENS[stage]:
                        reject(422, 'Stage token budget exceeded')
                    if session.stages.get(stage, 0) >= (2 if stage == 'match' else 1):
                        reject(409, 'Stage call budget exhausted')
                    if (sum(session.stages.values()) >= min(8, getattr(settings, 'VERIFICATION_MAX_AI_CALLS', 8))
                        or session.output_tokens + payload.max_tokens > min(10000, getattr(settings, 'VERIFICATION_MAX_OUTPUT_TOKENS', 10000))):
                        reject(409, 'Analysis AI budget exhausted')
                    session.stages[stage] = session.stages.get(stage, 0) + 1
                    session.output_tokens += payload.max_tokens
                    if stage == 'compare_repair':
                        session.limitations.append('Langflow menggunakan satu perbaikan perbandingan dalam anggaran analisis; tahap yang berhasil tidak diulang.')
                elif action == 'validate':
                    from app.models.langflow_models import validate_comparison
                    if not session.stages.get('compare') or session.comparison_checks >= 1 + session.stages.get('compare_repair', 0):
                        reject(409, 'Comparison validation unavailable')
                    session.comparison_checks += 1
                    try:
                        if payload.result is None:
                            raise ValueError('Invalid JSON')
                        result = validate_comparison(payload.result, session.claims, session.sources, is_image=session.input_type == 'image')
                    except ValueError:
                        session.comparison_invalid = True
                        return {'valid': False, 'remaining_seconds': session.remaining_seconds}
                    session.comparison_invalid = False
                    return {'valid': True, 'result': result, 'remaining_seconds': session.remaining_seconds}
                elif action == 'search':
                    await _search(session, payload)
                elif action == 'candidates':
                    await _candidates(session)
                    return {**session.envelope(), 'candidates': session.candidates}
                elif action == 'matches':
                    if session.matches_confirmed:
                        reject(409, 'Image matches already confirmed')
                    approved = {c['source_id'] for c in (session.candidates or [])}
                    if session.stages.get('match', 0) != len(approved):
                        reject(409, 'Candidate match AI calls have not been reserved')
                    ids = [m.source_id for m in payload.matches]
                    if len(ids) != len(set(ids)) or set(ids) != approved:
                        reject(422, 'Unapproved or duplicate candidate ID')
                    if any(m.match == 'SAME_IMAGE' and len(m.features.strip()) < 20 for m in payload.matches):
                        reject(422, 'Distinctive match features required')
                    session.matches_confirmed = True
                    session.matched_source_ids = {m.source_id for m in payload.matches if m.match == 'SAME_IMAGE'}
                return session.envelope()
        except TimeoutError:
            close_session(session_id)
            reject(410, 'Overall analysis deadline exceeded')




async def reserve_fallback(session: AnalysisSession) -> dict:
    """Reserve the sole backend comparison fallback without opening a callback stage."""
    async with session.lock:
        if not session.remaining_seconds:
            reject(410, 'Overall analysis deadline exceeded')
        if not session.registered or not session.claims or not session.sources or session.input_type == 'summary':
            reject(409, 'Fallback requires registered claims and retrieved evidence')
        if session.stages.get('native_fallback'):
            reject(409, 'Fallback already reserved')
        if (sum(session.stages.values()) >= min(8, getattr(settings, 'VERIFICATION_MAX_AI_CALLS', 8))
            or session.output_tokens + 2500 > min(10000, getattr(settings, 'VERIFICATION_MAX_OUTPUT_TOKENS', 10000))):
            reject(409, 'Analysis AI budget exhausted')
        session.stages['native_fallback'] = 1
        session.output_tokens += 2500
        return {'remaining_seconds': session.remaining_seconds,
                'remaining_calls': min(8, getattr(settings, 'VERIFICATION_MAX_AI_CALLS', 8)) - sum(session.stages.values()),
                'remaining_output_tokens': min(10000, getattr(settings, 'VERIFICATION_MAX_OUTPUT_TOKENS', 10000)) - session.output_tokens}
