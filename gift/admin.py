from django.contrib import admin
from .models import GiftCard, GiftCardTransaction


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = [
        'card_code', 'business', 'purchaser', 'recipient_name',
        'initial_amount', 'current_balance', 'currency', 'status',
        'issued_at', 'expires_at', 'is_active'
    ]
    list_filter = [
        'status', 'currency', 'business', 'issued_at', 'expires_at'
    ]
    search_fields = [
        'card_code', 'recipient_name', 'recipient_email', 'recipient_phone',
        'purchaser__first_name', 'purchaser__last_name', 'purchaser__email'
    ]
    readonly_fields = [
        'card_code', 'created_at', 'updated_at', 'issued_at',
        'is_active', 'is_expired', 'is_redeemed'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('card_code', 'business', 'purchaser', 'currency', 'status')
        }),
        ('Recipient Information', {
            'fields': ('recipient_name', 'recipient_email', 'recipient_phone', 'message')
        }),
        ('Amount Information', {
            'fields': ('initial_amount', 'current_balance')
        }),
        ('Dates', {
            'fields': ('issued_at', 'expires_at', 'redeemed_at')
        }),
        ('Additional Information', {
            'fields': ('payment', 'notes', 'created_at', 'updated_at', 'is_online_purchase')
        }),
        ('Status Properties', {
            'fields': ('is_active', 'is_expired', 'is_redeemed'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True
    is_active.short_description = 'Active'
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
    
    def is_redeemed(self, obj):
        return obj.is_redeemed
    is_redeemed.boolean = True
    is_redeemed.short_description = 'Redeemed'


@admin.register(GiftCardTransaction)
class GiftCardTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'gift_card', 'transaction_type', 'amount',
        'balance_before', 'balance_after', 'created_at'
    ]
    list_filter = [
        'transaction_type', 'created_at', 'gift_card__business'
    ]
    search_fields = [
        'gift_card__card_code', 'description'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('gift_card', 'transaction_type', 'amount')
        }),
        ('Balance Information', {
            'fields': ('balance_before', 'balance_after')
        }),
        ('Related Objects', {
            'fields': ('payment', 'appointment', 'created_by')
        }),
        ('Additional Information', {
            'fields': ('description', 'created_at')
        }),
    )
