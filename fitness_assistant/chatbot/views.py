import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import ChatMessage
from .services import coach
from .services.llm import LLMError, LLMNotConfigured

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1000
HISTORY_SHOWN = 50

SUGGESTIONS = [
    'Build me a 4-day upper/lower split',
    'How many calories and how much protein should I eat?',
    'Is creatine worth taking?',
    'How do I know when to take a deload week?',
]


def _rate_limited(user_id):
    """Simple fixed-window limiter (per user, per minute) to protect API quota/cost."""
    limit = getattr(settings, 'CHAT_RATE_LIMIT_PER_MINUTE', 15)
    key = f'chatbot_rate:{user_id}'
    if cache.add(key, 1, 60):
        return False
    try:
        return cache.incr(key) > limit
    except ValueError:  # key expired between add() and incr()
        cache.set(key, 1, 60)
        return False


@login_required
def chat_view(request):
    messages = ChatMessage.objects.filter(user=request.user).order_by('-created_at', '-id')[:HISTORY_SHOWN]
    history = [
        {'role': m.role, 'content': m.content, 'sources': m.sources}
        for m in reversed(list(messages))
    ]
    return render(request, 'chatbot/chat.html', {
        'history': history,
        'suggestions': SUGGESTIONS,
        'max_chars': MAX_MESSAGE_CHARS,
        'active_tab': 'chatbot',
    })


@login_required
@require_POST
def chat_message_api(request):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    message = payload.get('message') if isinstance(payload, dict) else None
    if not isinstance(message, str) or not message.strip():
        return JsonResponse({'error': 'Please type a message.'}, status=400)
    message = message.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        return JsonResponse({'error': f'Messages are limited to {MAX_MESSAGE_CHARS} characters.'}, status=400)

    if _rate_limited(request.user.id):
        return JsonResponse({'error': 'You are sending messages too quickly. Wait a moment and try again.'}, status=429)

    try:
        result = coach.answer(request.user, message)
    except LLMNotConfigured:
        logger.error('Chatbot LLM is not configured (check LLM_PROVIDER and API key in .env).')
        return JsonResponse({'error': 'The coach is not configured yet. Ask the site admin to add an API key.'}, status=503)
    except LLMError:
        logger.exception('LLM request failed')
        return JsonResponse({'error': 'The coach is unavailable right now. Please try again shortly.'}, status=502)

    return JsonResponse(result)


@login_required
@require_POST
def chat_clear_api(request):
    ChatMessage.objects.filter(user=request.user).delete()
    return JsonResponse({'status': 'success'})
