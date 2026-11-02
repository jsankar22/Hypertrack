from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from workouts.progression import lstm, rules
from workouts.progression.history import load_history


class Command(BaseCommand):
    help = "Train the Stage-2 LSTM progression model (needs PyTorch)."

    def add_arguments(self, parser):
        parser.add_argument('--epochs', type=int, default=25)

    def handle(self, *args, **opts):
        if not lstm.TORCH_OK:
            raise CommandError("PyTorch not installed. Run: pip install torch")
        histories = []
        for user in get_user_model().objects.all():
            for data in load_history(user).values():
                if len(data['entries']) >= rules.MIN_SESSIONS:
                    histories.append(data['entries'])
        self.stdout.write(f"Using {len(histories)} real exercise histories + synthetic lifters")
        acc, n = lstm.train(histories, epochs=opts['epochs'], log=self.stdout.write)
        self.stdout.write(self.style.SUCCESS(f"Saved model ({n} samples, val_acc={acc:.3f})"))
