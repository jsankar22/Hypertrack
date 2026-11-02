from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ChatMessage
from .services import coach
from .services.llm import LLMError, LLMNotConfigured, get_provider
from .services.prompts import build_profile_block, build_system_prompt

User = get_user_model()


class FakeProvider:
    def __init__(self, reply='Do 3 sets of 8.', error=None):
        self.reply, self.error, self.calls = reply, error, []

    def chat(self, system, messages, tools=None, handlers=None):
        self.calls.append({'system': system, 'messages': messages})
        if self.error:
            raise self.error
        return self.reply, []


class ChatbotViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='a@example.com', password='pw12345678', age=28,
            height_cm=Decimal('180'), weight_kg=Decimal('80'), goal='gain_muscle')
        self.other = User.objects.create_user(email='b@example.com', password='pw12345678')
        self.client.login(email='a@example.com', password='pw12345678')
        self.msg_url = reverse('chatbot_message_api')

    def _post(self, message):
        return self.client.post(self.msg_url, data={'message': message}, content_type='application/json')

    def test_pages_require_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('chatbot')).status_code, 302)
        self.assertEqual(self._post('hi').status_code, 302)

    def test_chat_page_renders_with_history(self):
        ChatMessage.objects.create(user=self.user, role='user', content='hello coach')
        ChatMessage.objects.create(user=self.other, role='user', content='secret of other user')
        resp = self.client.get(reverse('chatbot'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'hello coach')
        self.assertNotContains(resp, 'secret of other user')

    def test_message_validation(self):
        self.assertEqual(self._post('   ').status_code, 400)
        self.assertEqual(self._post('x' * 1001).status_code, 400)
        resp = self.client.post(self.msg_url, data='not json', content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(self.msg_url, data={'message': 123}, content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.client.get(self.msg_url).status_code, 405)

    def test_successful_message_is_saved(self):
        with patch('chatbot.services.coach.get_provider', return_value=FakeProvider()), \
                patch('chatbot.services.coach.rag.retrieve', return_value=[]):
            resp = self._post('Give me a workout')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['reply'], 'Do 3 sets of 8.')
        roles = list(ChatMessage.objects.filter(user=self.user).values_list('role', flat=True))
        self.assertEqual(roles, ['user', 'assistant'])

    def test_llm_failure_returns_502_and_saves_nothing(self):
        with patch('chatbot.services.coach.get_provider', return_value=FakeProvider(error=LLMError('down'))), \
                patch('chatbot.services.coach.rag.retrieve', return_value=[]):
            resp = self._post('hi there coach')
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_not_configured_returns_503(self):
        with patch('chatbot.services.coach.get_provider', side_effect=LLMNotConfigured('no key')):
            self.assertEqual(self._post('hi').status_code, 503)

    @override_settings(CHAT_RATE_LIMIT_PER_MINUTE=2)
    def test_rate_limit(self):
        with patch('chatbot.services.coach.get_provider', return_value=FakeProvider()), \
                patch('chatbot.services.coach.rag.retrieve', return_value=[]):
            codes = [self._post('hello').status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 429, 429])

    def test_clear_only_deletes_own_messages(self):
        ChatMessage.objects.create(user=self.user, role='user', content='mine')
        ChatMessage.objects.create(user=self.other, role='user', content='theirs')
        resp = self.client.post(reverse('chatbot_clear_api'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ChatMessage.objects.filter(user=self.user).count(), 0)
        self.assertEqual(ChatMessage.objects.filter(user=self.other).count(), 1)


class CoachServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='c@example.com', password='pw12345678', age=30,
            height_cm=Decimal('170'), weight_kg=Decimal('65'), goal='lose_weight')

    def test_history_and_profile_reach_the_model_and_email_does_not(self):
        ChatMessage.objects.create(user=self.user, role='user', content='first question')
        ChatMessage.objects.create(user=self.user, role='assistant', content='first answer')
        provider = FakeProvider()
        with patch('chatbot.services.coach.get_provider', return_value=provider), \
                patch('chatbot.services.coach.rag.retrieve', return_value=[]):
            coach.answer(self.user, 'And what about protein for a full day?')
        call = provider.calls[0]
        self.assertEqual([m['role'] for m in call['messages']], ['user', 'assistant', 'user'])
        self.assertIn('weight 65 kg', call['system'])
        self.assertIn('lose fat', call['system'])
        self.assertNotIn('c@example.com', call['system'])

    def test_sources_saved_and_passages_in_prompt(self):
        from .services.rag import Hit
        hits = [Hit('Creatine 3-5 g per day.', 'supplements_evidence.md', 'Supplements: What the Evidence Says', 0.9)]
        provider = FakeProvider()
        with patch('chatbot.services.coach.get_provider', return_value=provider), \
                patch('chatbot.services.coach.rag.retrieve', return_value=hits):
            result = coach.answer(self.user, 'How much creatine should I take each day?')
        self.assertEqual(result['sources'], ['Supplements: What the Evidence Says'])
        self.assertIn('REFERENCE MATERIAL', provider.calls[0]['system'])
        self.assertIn('Creatine 3-5 g per day.', provider.calls[0]['system'])
        saved = ChatMessage.objects.filter(user=self.user, role='assistant').first()
        self.assertEqual(saved.sources, ['Supplements: What the Evidence Says'])

    def test_short_followup_borrows_previous_question_for_retrieval(self):
        ChatMessage.objects.create(user=self.user, role='user', content='How much creatine should I take?')
        ChatMessage.objects.create(user=self.user, role='assistant', content='3-5 g daily.')
        with patch('chatbot.services.coach.get_provider', return_value=FakeProvider()), \
                patch('chatbot.services.coach.rag.retrieve', return_value=[]) as retrieve:
            coach.answer(self.user, 'Is it safe?')
        self.assertIn('creatine', retrieve.call_args.args[0])

    def test_profile_block_omits_missing_values(self):
        bare = User.objects.create_user(email='d@example.com', password='pw12345678')
        block = build_profile_block(bare)
        self.assertNotIn('height', block)
        self.assertIn('sex: not recorded', block)
        self.assertNotIn('REFERENCE MATERIAL\n', build_system_prompt(bare, []))


class ProviderSelectionTests(TestCase):
    @override_settings(LLM_PROVIDER='groq', GROQ_API_KEY='', GROQ_MODEL='m')
    def test_missing_groq_key(self):
        with self.assertRaises(LLMNotConfigured):
            get_provider()

    @override_settings(LLM_PROVIDER='anthropic', ANTHROPIC_API_KEY='k', ANTHROPIC_MODEL='m')
    def test_anthropic_selected(self):
        self.assertEqual(type(get_provider()).__name__, 'AnthropicProvider')

    @override_settings(LLM_PROVIDER='nope')
    def test_unknown_provider(self):
        with self.assertRaises(LLMNotConfigured):
            get_provider()
