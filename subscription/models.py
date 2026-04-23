from django.db import models
from main.models import SoftDeleteModel
from payment.models import CurrencyType


class SubscriptionTier(models.TextChoices):
    FREE = 'free', 'Free'
    BASIC = 'basic', 'Basic'
    STARTER = 'starter', 'Starter'
    PRO = 'pro', 'Pro'
    PREMIUM = 'premium', 'Premium'
    ENTERPRISE = 'enterprise', 'Enterprise'


class BillingCycle(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    YEARLY = 'yearly', 'Yearly'


class SubscriptionStatus(models.TextChoices):
    TRIALING = 'trialing', 'Trialing'
    ACTIVE = 'active', 'Active'
    PAST_DUE = 'past_due', 'Past Due'
    CANCELLED = 'canceled', 'Canceled'
    PAUSED = 'paused', 'Paused'
    UNPAID = 'unpaid', 'Unpaid'


class SubscriptionPlan(SoftDeleteModel):
    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=20, choices=SubscriptionTier.choices, default=SubscriptionTier.BASIC)
    description = models.TextField(blank=True, null=True)
    trial_days = models.PositiveIntegerField(default=0)

    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_quarterly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    stripe_product_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_price_id_monthly = models.CharField(max_length=255, blank=True, null=True)
    stripe_price_id_quarterly = models.CharField(max_length=255, blank=True, null=True)
    stripe_price_id_yearly = models.CharField(max_length=255, blank=True, null=True)

    max_staff = models.IntegerField(default=-1, help_text="-1 means unlimited")
    max_appointments_per_month = models.IntegerField(default=-1, help_text="-1 means unlimited")
    has_ai_receptionist = models.BooleanField(default=False)
    has_online_booking = models.BooleanField(default=True)
    has_analytics = models.BooleanField(default=False)
    has_sms_notifications = models.BooleanField(default=False)
    has_online_gift_cards = models.BooleanField(default=False)
    has_salary_management = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    ordering = models.IntegerField(default=0)
    
    currency = models.CharField(max_length=3, choices=CurrencyType.choices, default=CurrencyType.CAD)

    class Meta:
        ordering = ['ordering', 'tier']

    def __str__(self):
        return f"{self.name} ({self.tier})"


class BusinessSubscription(SoftDeleteModel):
    business = models.OneToOneField(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='subscription',
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIALING,
    )
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.business} — {self.plan.name} ({self.status})"
