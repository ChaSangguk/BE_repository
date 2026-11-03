from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        REPLY = "REPLY"
        PERSUASION_REWARD = "PERSUASION_REWARD"
        DEBATE_CLOSED = "DEBATE_CLOSED"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=17, choices=Type.choices)
    title = models.CharField(max_length=100)
    body = models.CharField(max_length=255, null=True, blank=True)
    target_type = models.CharField(max_length=20, null=True, blank=True)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"


class Scrap(models.Model):
    class TargetType(models.TextChoices):
        DEBATE = "DEBATE"
        OPINION = "OPINION"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    target_type = models.CharField(max_length=7, choices=TargetType.choices)
    target_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scraps"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "target_type", "target_id"],
                name="scrap_user_target_uniq",
            ),
        ]
