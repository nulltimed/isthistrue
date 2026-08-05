"""
Cliente unico de la API Anthropic con MODO SIMULADO.
Regla: ANTHROPIC_API_KEY vacia + DEBUG=True => mock automatico ([SIMULADO]).
Flag explicito MOCK_AGENTS=true/false en .env para forzar.
"""
import json
from django.conf import settings


def call(model, system, user_content, max_tokens=2000, mock_payload=None):
    """Devuelve texto. Si mock, devuelve mock_payload serializado."""
    if settings.MOCK_AGENTS:
        return json.dumps(mock_payload if mock_payload is not None
                          else {'simulated': True})
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{'role': 'user', 'content': user_content}])
    return ''.join(b.text for b in msg.content if getattr(b, 'type', '') == 'text')


def call_json(model, system, user_content, max_tokens=2000, mock_payload=None):
    """Como call() pero parsea JSON (el system prompt DEBE exigir solo-JSON)."""
    raw = call(model, system, user_content, max_tokens, mock_payload)
    raw = raw.strip().removeprefix('```json').removesuffix('```').strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {'error': 'json_parse', 'raw': raw[:500]}
