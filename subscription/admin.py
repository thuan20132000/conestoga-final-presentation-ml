from django.contrib import admin
from .models import SubscriptionPlan, BusinessSubscription


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'tier', 'price_monthly', 'price_quarterly', 'price_yearly',
        'trial_days', 'max_staff', 'has_ai_receptionist', 'has_online_booking',
        'has_analytics', 'has_sms_notifications', 'has_online_gift_cards', 'is_active', 'ordering', 'currency',
    ]
    list_filter = ['tier', 'is_active', 'has_ai_receptionist', 'has_online_booking', 'has_sms_notifications', 'has_online_gift_cards', 'has_salary_management']
    search_fields = ['name', 'description']
    readonly_fields = ['stripe_product_id', 'stripe_price_id_monthly', 'stripe_price_id_quarterly', 'stripe_price_id_yearly']
    fieldsets = (
        ('Plan Info', {
            'fields': ('name', 'tier', 'description', 'trial_days', 'is_active', 'ordering', 'currency'),
        }),
        ('Pricing', {
            'fields': ('price_monthly', 'price_quarterly', 'price_yearly'),
        }),
        ('Features', {
            'fields': ('max_staff', 'max_appointments_per_month', 'has_ai_receptionist', 'has_online_booking', 'has_analytics', 'has_sms_notifications', 'has_online_gift_cards', 'has_salary_management'),
        }),
        ('Stripe IDs (managed by sync command)', {
            'fields': ('stripe_product_id', 'stripe_price_id_monthly', 'stripe_price_id_quarterly', 'stripe_price_id_yearly'),
            'classes': ('collapse',),
        }),
    )


@admin.register(BusinessSubscription)
class BusinessSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'business', 'plan', 'billing_cycle', 'status',
        'current_period_start', 'current_period_end',
        'cancel_at_period_end', 'is_active',
    ]
    list_filter = ['status', 'billing_cycle', 'plan', 'cancel_at_period_end']
    search_fields = ['business__name', 'stripe_subscription_id', 'stripe_customer_id']
    readonly_fields = [
        'stripe_subscription_id', 'stripe_customer_id',
        'current_period_start', 'current_period_end',
        'cancelled_at', 'created_at', 'updated_at',
    ]
    raw_id_fields = ['business', 'plan']
