from django.conf import settings
from django.db import models


class CoinTransaction(models.Model):
    class Type(models.TextChoices):
        PURCHASE = "PURCHASE"
        AD_REWARD = "AD_REWARD"
        DEBATE_CREATE = "DEBATE_CREATE"
        REWARD = "REWARD"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.IntegerField()
    type = models.CharField(max_length=13, choices=Type.choices)
    balance_after = models.PositiveIntegerField()
    ref_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coin_transactions"


class CreditHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.IntegerField()
    reason = models.CharField(max_length=30)
    ref_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "credit_histories"


class Badge(models.Model):
    name = models.CharField(max_length=30)
    icon_url = models.URLField(max_length=500)
    required_credit = models.PositiveIntegerField()
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "badges"


class UserBadge(models.Model):
    pk = models.CompositePrimaryKey("user_id", "badge_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    badge = models.ForeignKey("economy.Badge", on_delete=models.CASCADE)
    acquired_at = models.DateTimeField(auto_now_add=True)
    is_representative = models.BooleanField(default=False)

    class Meta:
        db_table = "user_badges"
