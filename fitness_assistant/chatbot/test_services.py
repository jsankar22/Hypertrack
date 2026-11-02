"""Framework-free tests for calculators, chunking/retrieval and the LLM clients."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from .services import rag
from .services.calculators import TOOL_HANDLERS, calculate_nutrition_targets
from .services.llm import AnthropicProvider, GroqProvider, LLMError


class CalculatorTests(unittest.TestCase):
    def test_mifflin_st_jeor_bulk_example(self):
        r = calculate_nutrition_targets(80, 180, 25, 'male', 'moderate', 'bulk')
        self.assertEqual(r['bmr_kcal'], 1805)
        self.assertEqual(r['maintenance_kcal'], 2798)
        self.assertEqual(r['target_kcal'], 3078)
        self.assertEqual(r['protein_g'], 160)

    def test_female_cut_and_macros_add_up(self):
        r = calculate_nutrition_targets(65, 165, 30, 'female', 'light', 'cut')
        kcal = r['protein_g'] * 4 + r['carbs_g'] * 4 + r['fat_g'] * 9
        self.assertAlmostEqual(kcal, r['target_kcal'], delta=15)
        self.assertLess(r['target_kcal'], r['maintenance_kcal'])

    def test_goal_aliases_from_profile_values(self):
        self.assertEqual(calculate_nutrition_targets(80, 180, 25, 'male', 'moderate', 'gain_muscle')['goal'], 'bulk')
        self.assertEqual(calculate_nutrition_targets(80, 180, 25, 'male', 'moderate', 'lose_weight')['goal'], 'cut')

    def test_calorie_floor_applied(self):
        r = calculate_nutrition_targets(45, 150, 60, 'female', 'sedentary', 'cut')
        self.assertEqual(r['target_kcal'], 1200)
        self.assertTrue(any('floor' in n for n in r['notes']))

    def test_invalid_inputs_return_error(self):
        self.assertIn('error', calculate_nutrition_targets(80, 180, 25, '', 'moderate', 'bulk'))
        self.assertIn('error', calculate_nutrition_targets(80, 180, 25, 'male', 'hyper', 'bulk'))
        self.assertIn('error', calculate_nutrition_targets(80, 180, 25, 'male', 'moderate', 'shred'))
        self.assertIn('error', calculate_nutrition_targets('abc', 180, 25, 'male', 'moderate', 'bulk'))
        self.assertIn('error', calculate_nutrition_targets(80, 180, 16, 'male', 'moderate', 'bulk'))
        self.assertIn('error', calculate_nutrition_targets(800, 180, 25, 'male', 'moderate', 'bulk'))


class ChunkingAndRetrievalTests(unittest.TestCase):
    def test_chunks_respect_headings_and_size(self):
        text = '# Doc\n\n## Alpha\n' + ('Alpha sentence. ' * 100) + '\n\n## Beta\nShort beta text.'
        chunks = rag.chunk_text(text, 'Doc', max_chars=300)
        self.assertTrue(all(len(c) <= 300 + len('Doc > Alpha\n') for c in chunks))
        self.assertTrue(any(c.startswith('Doc > Beta\n') and 'beta' in c for c in chunks))
        self.assertFalse(any('Alpha' in c and 'beta' in c for c in chunks))  # never crosses a heading

    def test_load_chunks_uses_h1_as_title_and_ignores_other_files(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'a.md').write_text('# My Title\n\nHello world.', encoding='utf-8')
            (Path(d) / 'ignore.pdf').write_text('nope')
            chunks = rag.load_chunks(d)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].title, 'My Title')
        self.assertEqual(chunks[0].source, 'a.md')

    def test_keyword_retriever_on_real_knowledge_base(self):
        retriever = rag.KeywordRetriever(rag.load_chunks(rag.knowledge_dir()))
        expectations = {
            'how much creatine should I take daily': 'Supplements',
            'push pull legs exercises': 'Training Splits',
            'how many hours of sleep and when to deload': 'Recovery',
            'how do I calculate my BMR and TDEE': 'Calculating Calorie',
            'how much protein per kg for muscle': 'Nutrition Fundamentals',
            'chest pain while training': 'Safety',
        }
        for query, title_part in expectations.items():
            hits = retriever.search(query, k=3)
            self.assertTrue(hits, query)
            self.assertTrue(any(title_part in h.title for h in hits), f'{query!r} -> {[h.title for h in hits]}')

    def test_keyword_retriever_no_match(self):
        retriever = rag.KeywordRetriever(rag.load_chunks(rag.knowledge_dir()))
        self.assertEqual(retriever.search('zzzz qqqq', k=3), [])


def _resp(status, body):
    r = MagicMock()
    r.status_code = status
    r.text = json.dumps(body) if not isinstance(body, str) else body
    r.json.return_value = body
    return r


class GroqProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = GroqProvider('key', 'llama-3.3-70b-versatile')

    @patch('chatbot.services.llm.requests.post')
    def test_plain_reply(self, post):
        post.return_value = _resp(200, {'choices': [{'message': {'content': 'Lift heavy.'}}]})
        text, used = self.provider.chat('sys', [{'role': 'user', 'content': 'hi'}])
        self.assertEqual(text, 'Lift heavy.')
        self.assertEqual(used, [])
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['messages'][0], {'role': 'system', 'content': 'sys'})

    @patch('chatbot.services.llm.requests.post')
    def test_tool_call_round_trip(self, post):
        args = {'weight_kg': 80, 'height_cm': 180, 'age': 25, 'sex': 'male', 'activity_level': 'moderate', 'goal': 'bulk'}
        post.side_effect = [
            _resp(200, {'choices': [{'message': {'content': None, 'tool_calls': [
                {'id': 'c1', 'type': 'function',
                 'function': {'name': 'calculate_nutrition_targets', 'arguments': json.dumps(args)}}]}}]}),
            _resp(200, {'choices': [{'message': {'content': 'Eat 3078 kcal.'}}]}),
        ]
        from .services.calculators import TOOLS
        text, used = self.provider.chat('sys', [{'role': 'user', 'content': 'q'}], TOOLS, TOOL_HANDLERS)
        self.assertEqual(text, 'Eat 3078 kcal.')
        self.assertEqual(used, ['calculate_nutrition_targets'])
        second = post.call_args_list[1].kwargs['json']['messages']
        tool_msg = second[-1]
        self.assertEqual(tool_msg['role'], 'tool')
        self.assertEqual(tool_msg['tool_call_id'], 'c1')
        self.assertEqual(json.loads(tool_msg['content'])['target_kcal'], 3078)

    @patch('chatbot.services.llm.requests.post')
    def test_malformed_tool_call_retries_without_tools(self, post):
        post.side_effect = [
            _resp(400, '{"error":{"code":"tool_use_failed"}}'),
            _resp(200, {'choices': [{'message': {'content': 'Plain answer.'}}]}),
        ]
        from .services.calculators import TOOLS
        text, _ = self.provider.chat('sys', [{'role': 'user', 'content': 'q'}], TOOLS, TOOL_HANDLERS)
        self.assertEqual(text, 'Plain answer.')
        self.assertNotIn('tools', post.call_args_list[1].kwargs['json'])

    @patch('chatbot.services.llm.requests.post')
    def test_errors_raise_llm_error(self, post):
        post.return_value = _resp(429, 'rate limited')
        with self.assertRaises(LLMError):
            self.provider.chat('sys', [{'role': 'user', 'content': 'q'}])

    @patch('chatbot.services.llm.requests.post')
    def test_bad_tool_arguments_do_not_crash(self, post):
        post.side_effect = [
            _resp(200, {'choices': [{'message': {'content': None, 'tool_calls': [
                {'id': 'c1', 'type': 'function',
                 'function': {'name': 'calculate_nutrition_targets', 'arguments': '{not json'}}]}}]}),
            _resp(200, {'choices': [{'message': {'content': 'Could you share your weight?'}}]}),
        ]
        from .services.calculators import TOOLS
        text, _ = self.provider.chat('sys', [{'role': 'user', 'content': 'q'}], TOOLS, TOOL_HANDLERS)
        self.assertIn('weight', text)
        tool_msg = post.call_args_list[1].kwargs['json']['messages'][-1]
        self.assertIn('error', json.loads(tool_msg['content']))


class AnthropicProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = AnthropicProvider('key', 'claude-sonnet-5-5')

    @patch('chatbot.services.llm.requests.post')
    def test_tool_call_round_trip(self, post):
        args = {'weight_kg': 70, 'height_cm': 170, 'age': 30, 'sex': 'female', 'activity_level': 'light', 'goal': 'maintain'}
        post.side_effect = [
            _resp(200, {'content': [{'type': 'text', 'text': 'Let me calculate.'},
                                    {'type': 'tool_use', 'id': 't1', 'name': 'calculate_nutrition_targets', 'input': args}]}),
            _resp(200, {'content': [{'type': 'text', 'text': 'About 2000 kcal.'}]}),
        ]
        from .services.calculators import TOOLS
        text, used = self.provider.chat('sys', [{'role': 'user', 'content': 'q'}], TOOLS, TOOL_HANDLERS)
        self.assertEqual(text, 'About 2000 kcal.')
        self.assertEqual(used, ['calculate_nutrition_targets'])
        first = post.call_args_list[0].kwargs
        self.assertEqual(first['headers']['x-api-key'], 'key')
        self.assertEqual(first['json']['system'], 'sys')
        self.assertIn('input_schema', first['json']['tools'][0])
        follow_up = post.call_args_list[1].kwargs['json']['messages']
        self.assertEqual(follow_up[-1]['content'][0]['type'], 'tool_result')
        self.assertEqual(follow_up[-1]['content'][0]['tool_use_id'], 't1')

    @patch('chatbot.services.llm.requests.post')
    def test_http_error(self, post):
        post.return_value = _resp(500, 'boom')
        with self.assertRaises(LLMError):
            self.provider.chat('sys', [{'role': 'user', 'content': 'q'}])


if __name__ == '__main__':
    unittest.main()
