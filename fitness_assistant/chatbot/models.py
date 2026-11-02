from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    """One turn of a user's conversation with the fitness coach."""

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    # Titles of the reference documents retrieved for an assistant reply.
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['user', 'created_at'], name='chat_user_created_idx'),
        ]

    def __str__(self):
        return f"{self.user.email} [{self.role}] {self.content[:40]}"
