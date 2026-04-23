from rest_framework import serializers
from .models import SubscriptionPlan, BusinessSubscription, BillingCycle
from django.utils.translation import gettext_lazy as _


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'tier',
            'description',
            'trial_days',
            'price_monthly',
            'price_quarterly',
            'price_yearly',
            'max_staff',
            'max_appointments_per_month',
            'has_ai_receptionist',
            'has_online_booking',
            'has_analytics',
            'has_sms_notifications',
            'has_online_gift_cards',
            'has_salary_management',
            'is_active',
            'ordering',
            'currency',
        ]
        read_only_fields = fields


class BusinessSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = BusinessSubscription
        fields = [
            'id',
            'business',
            'plan',
            'billing_cycle',
            'status',
            'stripe_subscription_id',
            'stripe_customer_id',
            'current_period_start',
            'current_period_end',
            'cancel_at_period_end',
            'trial_end',
            'cancelled_at',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class BusinessSubscriptionCreateSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    billing_cycle = serializers.ChoiceField(choices=BillingCycle.choices)
    success_url = serializers.URLField(help_text="URL to redirect after successful subscription",)
    cancel_url = serializers.URLField(help_text="URL to redirect if user cancels subscription")

    def validate_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(_("Subscription plan not found or inactive."))
        return value


class CancelSubscriptionSerializer(serializers.Serializer):
    immediate = serializers.BooleanField(default=False, required=False)


class ChangePlanSerializer(serializers.Serializer):
    new_plan_id = serializers.IntegerField()
    new_billing_cycle = serializers.ChoiceField(choices=BillingCycle.choices)

    def validate_new_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError(_("Subscription plan not found or inactive."))
        return value
