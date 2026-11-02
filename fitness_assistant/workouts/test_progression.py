import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import SessionExercise, SessionSet, WorkoutSession
from .progression import get_progression_for_user, rules
from .progression.history import Entry
from .progression.service import INSUFFICIENT_MSG

User = get_user_model()
D = datetime.date


def mk(date, w, reps, sets=3):
    return Entry(date=date, weight=float(w), reps=reps, sets=sets,
                 volume=float(w * reps * sets), best_reps_at_top=reps)


def series(start, spec, gap=3):
    return [mk(start + datetime.timedelta(days=gap * i), w, r) for i, (w, r) in enumerate(spec)]


class RuleTests(TestCase):
    def test_push_when_goal_reps_hit(self):
        e = series(D(2026, 9, 1), [(57.5, 8), (60, 8), (62.5, 8)])
        r = rules.predict('Squat', e, today=e[-1].date + datetime.timedelta(days=2))
        self.assertEqual(r['recommendation'], rules.PUSH)
        self.assertEqual(r['next_weight'], 65.0)

    def test_maintain_when_reps_short_of_goal(self):
        e = series(D(2026, 9, 1), [(60, 6), (60, 6), (60, 7)])
        r = rules.predict('Bench Press', e, today=e[-1].date + datetime.timedelta(days=2))
        self.assertEqual(r['recommendation'], rules.MAINTAIN)
        self.assertEqual(r['next_weight'], 60.0)

    def test_reduce_when_struggling(self):
        e = series(D(2026, 9, 1), [(60, 8), (65, 6), (65, 3)])
        r = rules.predict('Squat', e, today=e[-1].date + datetime.timedelta(days=2))
        self.assertEqual(r['recommendation'], rules.REDUCE)

    def test_short_gap_not_penalised(self):
        e = series(D(2026, 9, 1), [(57.5, 8), (60, 8), (62.5, 8)])
        r = rules.predict('Squat', e, today=e[-1].date + datetime.timedelta(days=3))
        self.assertEqual(r['recommendation'], rules.PUSH)
        self.assertEqual(r['days_since_last_workout'], 3)

    def test_break_resumes_at_last_successful_weight(self):
        # last logged session was a failure (62.5x4); last success was 60x8
        e = series(D(2026, 9, 1), [(57.5, 8), (60, 8), (62.5, 4)])
        r = rules.predict('Squat', e, today=e[-1].date + datetime.timedelta(days=9))
        self.assertTrue(r['on_break'])
        self.assertEqual(r['recommendation'], rules.MAINTAIN)
        self.assertEqual(r['next_weight'], 60.0)
        self.assertEqual(r['last_successful_weight'], 60.0)
        self.assertEqual(r['headline'], 'RESUME')

    def test_long_break_eases_back(self):
        e = series(D(2026, 7, 1), [(57.5, 8), (60, 8), (60, 8)])
        r = rules.predict('Squat', e, today=e[-1].date + datetime.timedelta(days=40))
        self.assertLess(r['next_weight'], 60.0)
        self.assertNotEqual(r['recommendation'], rules.REDUCE)  # not a "failure"


class IntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='p@example.com', password='pw12345678')

    def add_session(self, date, name, sets):
        s = WorkoutSession.objects.create(user=self.user, date=date)
        ex = SessionExercise.objects.create(session=s, name=name)
        for i, (reps, w) in enumerate(sets, 1):
            SessionSet.objects.create(exercise=ex, set_number=i, reps=reps, weight=Decimal(str(w)))

    def test_insufficient_history_message(self):
        self.add_session(D(2026, 9, 1), 'Squat', [(8, 60)])
        res = get_progression_for_user(self.user, today=D(2026, 9, 3))
        self.assertFalse(res['ready'])
        self.assertEqual(res['message'], INSUFFICIENT_MSG)

    def test_prediction_from_sessions(self):
        for i, w in enumerate([57.5, 60, 62.5]):
            self.add_session(D(2026, 9, 1) + datetime.timedelta(days=3 * i), 'Squat', [(8, w)] * 3)
        res = get_progression_for_user(self.user, today=D(2026, 9, 9))
        self.assertTrue(res['ready'])
        self.assertEqual(res['items'][0]['next_weight'], 65.0)

    def test_dashboard_and_page_render(self):
        self.client.login(email='p@example.com', password='pw12345678')
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, INSUFFICIENT_MSG)
        self.assertEqual(self.client.get(reverse('workout_progression')).status_code, 200)

    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse('workout_progression')).status_code, 302)
