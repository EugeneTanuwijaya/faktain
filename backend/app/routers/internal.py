"""Private evidence callbacks; never authenticated with end-user credentials."""
import hmac
import json

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.services.analysis_session_service import dispatch

router = APIRouter(prefix='/internal', include_in_schema=False)


@router.post('/analyses/{analysis_id}/{action}')
async def analysis_callback(analysis_id: str, action: str, request: Request):
    expected = getattr(settings, 'LANGFLOW_SERVICE_KEY', '')
    supplied = request.headers.get('X-Faktain-Service-Key', '')
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail='Invalid service authentication')
    try:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                raise HTTPException(status_code=413, detail='Callback payload too large')
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=422, detail='Invalid callback JSON') from None
    return await dispatch(analysis_id, action, payload)
