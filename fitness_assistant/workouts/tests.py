import datetime
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    Exercise, SplitDay, WorkoutLog, WorkoutSession, WorkoutSplit, generate_suggested_split,
)

User = get_user_model()


def post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type='application/json')


class WorkoutBase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(email='user1@example.com', password='password123')
        self.user2 = User.objects.create_user(email='user2@example.com', password='password123')
        self.client.login(email='user1@example.com', password='password123')

    def session_payload(self, **overrides):
        payload = {
            'date': '2026-06-02',
            'dayId': None,
            'notes': 'Felt strong',
            'duration': 45,
            'calories': 200,
            'exercises': [
                {'name': 'Barbell Bench Press', 'group': 'Chest', 'rest': 90,
                 'sets': [{'reps': 10, 'weight': 60}, {'reps': 10, 'weight': 60}, {'reps': 8, 'weight': 65}]},
                {'name': 'Cable Fly Special', 'group': 'Chest', 'rest': None, 'sets': [{'reps': 12, 'weight': 20}]},
                {'name': 'Skipped Exercise', 'group': '', 'rest': None, 'sets': []},
            ],
        }
        payload.update(overrides)
        return payload


class SuggestionTests(TestCase):
    def test_suggestions_cover_every_day_count(self):
        for n in range(1, 8):
            days = generate_suggested_split(n)
            self.assertEqual(len(days), n)
            for d in days:
                self.assertTrue(d['label'])
                self.assertTrue(d['muscle_focus'])
                self.assertTrue(d['exercises'])

    def test_push_day_matches_design(self):
        push = generate_suggested_split(3)[0]
        self.assertEqual(push['label'], 'Push Day')
        self.assertEqual(
            [e['exercise'] for e in push['exercises']],
            ['Barbell Bench Press', 'Incline Dumbbell Press', 'Chest Fly Machine', 'Shoulder Press', 'Tricep Pushdown'],
        )


class LogPageTests(WorkoutBase):
    def test_login_required(self):
        self.client.logout()
        for name in ['workout_list', 'workout_history', 'workout_split']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_log_page_without_split(self):
        resp = self.client.get(reverse('workout_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Workout Log')
        self.assertEqual(resp.context['state']['exercises'], [])

    def test_generate_split_from_log_page_then_load_day(self):
        resp = self.client.post(reverse('workout_split_generate'), {'days_per_week': 6, 'next': 'log'})
        self.assertRedirects(resp, reverse('workout_list'))
        split = WorkoutSplit.objects.get(user=self.user1)
        self.assertEqual(split.days.count(), 6)

        page = self.client.get(reverse('workout_list'))
        self.assertEqual(page.context['selected_day'].label, 'Push Day')
        names = [e['name'] for e in page.context['state']['exercises']]
        self.assertEqual(names[0], 'Barbell Bench Press')
        self.assertEqual(page.context['focus'], ['Chest', 'Shoulders', 'Triceps'])

    def test_generate_rejects_bad_days(self):
        self.client.post(reverse('workout_split_generate'), {'days_per_week': 9})
        self.assertFalse(WorkoutSplit.objects.filter(user=self.user1).exists())

    def test_default_day_rotates_after_a_session(self):
        self.client.post(reverse('workout_split_generate'), {'days_per_week': 3})
        push = SplitDay.objects.get(split__user=self.user1, label='Push Day')
        post_json(self.client, reverse('workout_session_save'),
                  self.session_payload(date='2026-06-01', dayId=push.id))
        page = self.client.get(reverse('workout_list') + '?date=2026-06-02')
        self.assertEqual(page.context['selected_day'].label, 'Pull Day')


class SaveSessionTests(WorkoutBase):
    def test_save_creates_session_sets_and_mirror_logs(self):
        resp = post_json(self.client, reverse('workout_session_save'), self.session_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

        session = WorkoutSession.objects.get(user=self.user1)
        self.assertEqual(session.duration_min, 45)
        self.assertEqual(session.exercises.count(), 2)          # empty exercise skipped
        bench = session.exercises.get(name='Barbell Bench Press')
        self.assertEqual([(s.reps, s.weight) for s in bench.sets.all()],
                         [(10, Decimal('60')), (10, Decimal('60')), (8, Decimal('65'))])

        # Dashboard compatibility: grouped mirror rows with correct volume
        logs = WorkoutLog.objects.filter(user=self.user1, exercise='Barbell Bench Press').order_by('id')
        self.assertEqual([(l.sets, l.reps, l.volume) for l in logs],
                         [(2, 10, Decimal('1200.00')), (1, 8, Decimal('520.00'))])

    def test_new_exercise_added_to_library(self):
        post_json(self.client, reverse('workout_session_save'), self.session_payload())
        self.assertTrue(Exercise.objects.filter(user=self.user1, name='Cable Fly Special', muscle_group='Chest').exists())
        self.assertFalse(Exercise.objects.filter(user=self.user1, name='Barbell Bench Press').exists())  # built-in

    def test_resaving_same_date_replaces(self):
        url = reverse('workout_session_save')
        post_json(self.client, url, self.session_payload())
        post_json(self.client, url, self.session_payload(exercises=[
            {'name': 'Squat', 'group': 'Legs', 'rest': None, 'sets': [{'reps': 5, 'weight': 100}]}]))
        self.assertEqual(WorkoutSession.objects.filter(user=self.user1).count(), 1)
        self.assertEqual(WorkoutLog.objects.filter(user=self.user1).count(), 1)

    def test_reopen_saved_session(self):
        post_json(self.client, reverse('workout_session_save'), self.session_payload())
        page = self.client.get(reverse('workout_list') + '?date=2026-06-02')
        state = page.context['state']
        self.assertTrue(state['hasSession'])
        self.assertEqual(state['notes'], 'Felt strong')
        self.assertEqual(len(state['exercises'][0]['sets']), 3)

    def test_validation_errors(self):
        url = reverse('workout_session_save')
        no_sets = self.session_payload(exercises=[{'name': 'Squat', 'sets': []}])
        self.assertEqual(post_json(self.client, url, no_sets).status_code, 400)
        bad_reps = self.session_payload(exercises=[{'name': 'Squat', 'sets': [{'reps': 0, 'weight': 10}]}])
        self.assertEqual(post_json(self.client, url, bad_reps).status_code, 400)
        bad_date = self.session_payload(date='nope')
        self.assertEqual(post_json(self.client, url, bad_date).status_code, 400)
        self.assertEqual(self.client.post(url, data='not json', content_type='application/json').status_code, 400)
        self.assertEqual(WorkoutSession.objects.count(), 0)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse('workout_session_save')).status_code, 405)

    def test_cannot_attach_other_users_day(self):
        WorkoutSplit.objects.create(user=self.user2, days_per_week=1)
        other = SplitDay.objects.create(split=self.user2.workout_split, label='Theirs')
        post_json(self.client, reverse('workout_session_save'), self.session_payload(dayId=other.id))
        self.assertIsNone(WorkoutSession.objects.get(user=self.user1).split_day)


class HistoryTests(WorkoutBase):
    def test_history_lists_and_deletes(self):
        post_json(self.client, reverse('workout_session_save'), self.session_payload())
        page = self.client.get(reverse('workout_history'))
        self.assertContains(page, 'Custom Workout')
        row = page.context['rows'][0]
        self.assertEqual((row['count'], row['sets']), (2, 4))

        session = WorkoutSession.objects.get()
        resp = self.client.post(reverse('workout_session_delete', args=[session.id]))
        self.assertRedirects(resp, reverse('workout_history'))
        self.assertFalse(WorkoutSession.objects.exists())
        self.assertFalse(WorkoutLog.objects.exists())            # mirror rows cascade

    def test_empty_history(self):
        self.assertContains(self.client.get(reverse('workout_history')), 'No saved workouts yet.')

    def test_cannot_delete_others_session(self):
        post_json(self.client, reverse('workout_session_save'), self.session_payload())
        session = WorkoutSession.objects.get()
        self.client.logout()
        self.client.login(email='user2@example.com', password='password123')
        self.assertEqual(self.client.post(reverse('workout_session_delete', args=[session.id])).status_code, 404)
        self.assertTrue(WorkoutSession.objects.exists())


class SplitTests(WorkoutBase):
    def save_day(self, **payload):
        data = {'id': None, 'label': 'Arm Day', 'muscleFocus': 'Biceps, Triceps',
                'exercises': [{'exercise': 'Bicep Curl', 'sets': 3, 'reps': 12},
                              {'exercise': 'Tricep Pushdown', 'sets': 3, 'reps': 12}]}
        data.update(payload)
        return post_json(self.client, reverse('workout_split_day_save'), data)

    def test_create_edit_delete_day(self):
        resp = self.save_day()
        self.assertEqual(resp.status_code, 200)
        day = SplitDay.objects.get(split__user=self.user1)
        self.assertEqual(day.exercises.count(), 2)

        self.save_day(id=day.id, label='Arms', exercises=[{'exercise': 'Hammer Curl', 'sets': 4, 'reps': 10}])
        day.refresh_from_db()
        self.assertEqual(day.label, 'Arms')
        self.assertEqual(list(day.exercises.values_list('exercise', flat=True)), ['Hammer Curl'])

        page = self.client.get(reverse('workout_split'))
        self.assertContains(page, 'Arms')

        self.client.post(reverse('workout_split_day_delete', args=[day.id]))
        self.assertFalse(SplitDay.objects.filter(pk=day.id).exists())

    def test_editor_pages_render(self):
        self.save_day()
        day = SplitDay.objects.get()
        self.assertEqual(self.client.get(reverse('workout_split_day_add')).status_code, 200)
        self.assertEqual(self.client.get(reverse('workout_split_day_edit', args=[day.id])).status_code, 200)

    def test_save_requires_label(self):
        self.assertEqual(self.save_day(label='  ').status_code, 400)

    def test_cannot_edit_others_day(self):
        self.client.logout()
        self.client.login(email='user2@example.com', password='password123')
        self.save_day()
        theirs = SplitDay.objects.get(split__user=self.user2)
        self.client.logout()
        self.client.login(email='user1@example.com', password='password123')
        self.assertEqual(self.client.get(reverse('workout_split_day_edit', args=[theirs.id])).status_code, 404)
        self.assertEqual(self.save_day(id=theirs.id).status_code, 404)

    def test_reset_split(self):
        self.save_day()
        self.client.post(reverse('workout_split_reset'))
        self.assertFalse(WorkoutSplit.objects.filter(user=self.user1).exists())


class LegacyLinkTests(WorkoutBase):
    def test_old_add_url_redirects_to_log(self):
        self.assertRedirects(self.client.get(reverse('workout_add')), reverse('workout_list'))

    def test_dashboard_still_reads_mirrored_logs(self):
        from django.utils import timezone
        today = timezone.localdate().isoformat()
        post_json(self.client, reverse('workout_session_save'), self.session_payload(date=today))
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        # 2*10*60 + 1*8*65 + 1*12*20 = 1200 + 520 + 240
        self.assertEqual(resp.context['weekly_volume'], Decimal('1960.00'))
        self.assertEqual(len(resp.context['recent_workouts']), 3)
