"""Thin LLM client for Groq (Llama 3) and Anthropic (Claude).

Both providers are called over plain HTTPS with `requests`, so no extra SDK
is required. Each provider supports a small tool-calling loop so the model can
call `calculate_nutrition_targets` instead of doing arithmetic itself.

Switch provider with LLM_PROVIDER=groq|anthropic in .env.
"""
import json
import logging

import requests

logger = logging.getLogger(__name__)

GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_VERSION = '2023-06-01'


class LLMError(Exception):
    """The provider failed or returned something unusable."""


class LLMNotConfigured(LLMError):
    """No API key / unknown provider."""


class _ToolCallFormatError(LLMError):
    """Model produced a malformed tool call (seen occasionally with Llama)."""


def _run_tool(name, raw_args, handlers):
    handler = handlers.get(name)
    if handler is None:
        return {'error': f'Unknown tool {name}'}
    try:
        args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args or '{}')
        return handler(**args)
    except Exception as exc:  # bad args from the model must not crash the request
        logger.warning('Tool %s failed: %s', name, exc)
        return {'error': f'Tool call failed: {exc}'}


class BaseProvider:
    max_rounds = 3
    timeout = 45

    def chat(self, system, messages, tools=None, handlers=None):
        """Run the conversation to completion. Returns (reply_text, tools_used)."""
        handlers = handlers or {}
        msgs = list(messages)
        use_tools = bool(tools)
        tools_used = []

        for _ in range(self.max_rounds):
            try:
                data = self._post(system, msgs, tools if use_tools else None)
            except _ToolCallFormatError:
                # Retry once as a plain chat; only safe before any tool round-trip.
                if use_tools and len(msgs) == len(messages):
                    use_tools = False
                    continue
                raise LLMError('The model produced an invalid tool call.')

            text, calls, assistant_msg = self._parse(data)
            if not calls:
                if not text:
                    raise LLMError('The model returned an empty reply.')
                return text, tools_used

            msgs.append(assistant_msg)
            results = []
            for call in calls:
                tools_used.append(call['name'])
                results.append((call, _run_tool(call['name'], call['args'], handlers)))
            msgs.extend(self._tool_result_messages(results))

        raise LLMError('The model kept calling tools without answering.')

    # -- provider hooks -------------------------------------------------
    def _post(self, system, msgs, tools):
        raise NotImplementedError

    def _parse(self, data):
        raise NotImplementedError

    def _tool_result_messages(self, results):
        raise NotImplementedError


class GroqProvider(BaseProvider):
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def _post(self, system, msgs, tools):
        payload = {
            'model': self.model,
            'messages': [{'role': 'system', 'content': system}] + msgs,
            'temperature': 0.4,
            # Reasoning models (gpt-oss, qwen3) spend part of this budget on hidden thinking.
            'max_tokens': 2500,
        }
        if 'gpt-oss' in self.model:
            payload['reasoning_effort'] = 'low'  # keep replies fast and leave room for the answer
        if tools:
            payload['tools'] = [
                {'type': 'function', 'function': t} for t in tools
            ]
            payload['tool_choice'] = 'auto'
        try:
            resp = requests.post(
                GROQ_URL,
                headers={'Authorization': f'Bearer {self.api_key}'},
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMError(f'Could not reach Groq: {exc}') from exc

        if resp.status_code == 400 and 'tool_use_failed' in resp.text:
            raise _ToolCallFormatError(resp.text)
        if resp.status_code != 200:
            raise LLMError(f'Groq returned {resp.status_code}: {resp.text[:300]}')
        return resp.json()

    def _parse(self, data):
        try:
            message = data['choices'][0]['message']
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError('Unexpected response from Groq.') from exc
        calls = [
            {'id': c['id'], 'name': c['function']['name'], 'args': c['function'].get('arguments')}
            for c in (message.get('tool_calls') or [])
        ]
        assistant_msg = {
            'role': 'assistant',
            'content': message.get('content') or '',
            'tool_calls': message.get('tool_calls'),
        }
        return (message.get('content') or '').strip(), calls, assistant_msg

    def _tool_result_messages(self, results):
        return [
            {'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps(result)}
            for call, result in results
        ]


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def _post(self, system, msgs, tools):
        payload = {
            'model': self.model,
            'max_tokens': 1000,
            'system': system,
            'messages': msgs,
        }
        if tools:
            payload['tools'] = [
                {'name': t['name'], 'description': t['description'], 'input_schema': t['parameters']}
                for t in tools
            ]
        try:
            resp = requests.post(
                ANTHROPIC_URL,
                headers={
                    'x-api-key': self.api_key,
                    'anthropic-version': ANTHROPIC_VERSION,
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise LLMError(f'Could not reach Anthropic: {exc}') from exc
        if resp.status_code != 200:
            raise LLMError(f'Anthropic returned {resp.status_code}: {resp.text[:300]}')
        return resp.json()

    def _parse(self, data):
        blocks = data.get('content')
        if not isinstance(blocks, list):
            raise LLMError('Unexpected response from Anthropic.')
        text = ''.join(b.get('text', '') for b in blocks if b.get('type') == 'text').strip()
        calls = [
            {'id': b['id'], 'name': b['name'], 'args': b.get('input') or {}}
            for b in blocks if b.get('type') == 'tool_use'
        ]
        return text, calls, {'role': 'assistant', 'content': blocks}

    def _tool_result_messages(self, results):
        return [{
            'role': 'user',
            'content': [
                {'type': 'tool_result', 'tool_use_id': call['id'], 'content': json.dumps(result)}
                for call, result in results
            ],
        }]


def get_provider():
    """Build the provider selected in Django settings."""
    from django.conf import settings

    name = (getattr(settings, 'LLM_PROVIDER', 'groq') or 'groq').lower()
    if name == 'groq':
        key = getattr(settings, 'GROQ_API_KEY', '')
        if not key:
            raise LLMNotConfigured('GROQ_API_KEY is not set.')
        return GroqProvider(key, settings.GROQ_MODEL)
    if name == 'anthropic':
        key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not key:
            raise LLMNotConfigured('ANTHROPIC_API_KEY is not set.')
        return AnthropicProvider(key, settings.ANTHROPIC_MODEL)
    raise LLMNotConfigured(f"Unknown LLM_PROVIDER '{name}'. Use 'groq' or 'anthropic'.")
