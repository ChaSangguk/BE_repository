from django.conf import settings
from django.db import models


class Report(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        ACCEPTED = "ACCEPTED"
        REJECTED = "REJECTED"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    opinion = models.ForeignKey("discussions.Opinion", on_delete=models.PROTECT)
    reason = models.CharField(max_length=255)
    status = models.CharField(
        max_length=8,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reports"


class BannedWord(models.Model):
    class Level(models.TextChoices):
        BLOCK = "BLOCK"
        MASK = "MASK"

    word = models.CharField(max_length=50, unique=True)
    level = models.CharField(max_length=5, choices=Level.choices, default=Level.BLOCK)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "banned_words"
