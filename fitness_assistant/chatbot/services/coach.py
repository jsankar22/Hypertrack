"""Orchestrates one chatbot turn: retrieve -> build prompt -> call LLM -> save."""
import logging

from ..models import ChatMessage
from . import rag
from .calculators import TOOL_HANDLERS, TOOLS
from .llm import get_provider
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10          # past messages sent to the model
SHORT_QUERY_WORDS = 6       # follow-ups shorter than this borrow the previous question for retrieval


def _history_messages(user):
    recent = list(ChatMessage.objects.filter(user=user).order_by('-created_at', '-id')[:HISTORY_LIMIT])[::-1]
    while recent and recent[0].role != 'user':  # conversations must start with a user turn
        recent.pop(0)
    return [{'role': m.role, 'content': m.content} for m in recent]


def _retrieval_query(history, message):
    if len(message.split()) >= SHORT_QUERY_WORDS:
        return message
    previous = [m['content'] for m in history if m['role'] == 'user']
    return f'{previous[-1]} {message}' if previous else message


def answer(user, message):
    """Return {'reply', 'sources', 'tools_used'}. Raises LLMError subclasses on failure."""
    provider = get_provider()  # fail fast if not configured
    history = _history_messages(user)
    hits = rag.retrieve(_retrieval_query(history, message))
    system = build_system_prompt(user, hits)

    reply, tools_used = provider.chat(
        system,
        history + [{'role': 'user', 'content': message}],
        tools=TOOLS,
        handlers=TOOL_HANDLERS,
    )

    sources = list(dict.fromkeys(h.title for h in hits))
    # Save only after success so history never contains an unanswered user turn.
    ChatMessage.objects.create(user=user, role='user', content=message)
    ChatMessage.objects.create(user=user, role='assistant', content=reply, sources=sources)
    return {'reply': reply, 'sources': sources, 'tools_used': tools_used}
