from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    PaymentMethod, PaymentGateway, Payment, PaymentSplit, Refund, PaymentTransaction, PaymentDiscount
)

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'payment_type', 'is_active', 'is_default', 'processing_fees']
    list_filter = ['business', 'payment_type', 'is_active', 'is_default']
    search_fields = ['name', 'business__name', 'description']
    ordering = ['business__name', 'name']
    fieldsets = (
        ('Basic Info', {
            'fields': ('business', 'name', 'payment_type', 'description')
        }),
        ('Status', {
            'fields': ('is_active', 'is_default')
        }),
        ('Fees', {
            'fields': ('processing_fee_percentage', 'processing_fee_fixed'),
            'description': 'Configurable processing fees'
        }),
    )

    def processing_fees(self, obj):
        if obj.processing_fee_percentage or obj.processing_fee_fixed:
            return f"{obj.processing_fee_percentage:.2%} + ${obj.processing_fee_fixed:.2f}"
        return "No fees"
    processing_fees.short_description = 'Processing Fees'

@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'gateway_type', 'is_active', 'is_default', 'test_mode']
    list_filter = ['business', 'gateway_type', 'is_active', 'is_default', 'test_mode']
    search_fields = ['name', 'business__name']

class PaymentSplitInline(admin.TabularInline):
    model = PaymentSplit
    extra = 0
    fields = ['payment_method', 'amount', 'processing_fee', 'status', 'external_transaction_id']
    readonly_fields = ['created_at', 'updated_at']

class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    fields = ['refund_type', 'refund_reason', 'amount', 'status', 'external_refund_id', 'notes']
    readonly_fields = ['created_at', 'updated_at']

class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    fields = ['event_type', 'description', 'amount', 'created_by']
    readonly_fields = ['created_at']
    
class PaymentDiscountInline(admin.TabularInline):
    model = PaymentDiscount
    extra = 0
    fields = ['discount_amount', 'discount_percentage', 'discount_code', 'discount_description']
    readonly_fields = ['created_at']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_id', 'client', 'business', 'appointment', 'amount', 'currency',
        'payment_method', 'status', 'transaction_type', 'created_at', 'completed_at'
    ]
    list_filter = ['business']
    search_fields = [
        'payment_id', 'client__name', 'client__email', 'external_transaction_id', 'appointment__service__name'
    ]
    readonly_fields = [
        'payment_id', 'created_at', 'updated_at', 'processed_at', 'completed_at',
        'processing_fee', 'net_amount'
    ]
    ordering = ['-created_at']
    fieldsets = (
        ('Payment Info', {'fields': (
            'payment_id', 'business', 'client', 'appointment', 'amount', 'currency', 'transaction_type'
        )}),
        ('Method & Status', {'fields': (
            'payment_method', 'status', 'external_transaction_id', 'gateway_response', 'failure_reason'
        )}),
        ('Financial', {
            'fields': ('processing_fee', 'net_amount'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes', 'internal_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Staff', {
            'fields': ('processed_by',),
            'classes': ('collapse',)
        }),
    )
    inlines = [PaymentSplitInline, RefundInline, PaymentTransactionInline, PaymentDiscountInline]

@admin.register(PaymentDiscount)
class PaymentDiscountAdmin(admin.ModelAdmin):
    list_display = ['payment', 'discount_amount', 'discount_percentage', 'discount_code', 'discount_description', 'created_at']
    list_filter = ['payment__status', 'created_at']
    search_fields = ['payment__payment_id', 'discount_code', 'discount_description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def payment_link(self, obj):
        url = reverse('admin:payment_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_id)
    payment_link.short_description = 'Payment'
    payment_link.admin_order_field = 'payment__payment_id'

@admin.register(PaymentSplit)
class PaymentSplitAdmin(admin.ModelAdmin):
    list_display = [
        'payment_link', 'payment_method', 'amount', 'processing_fee', 'status_display', 'created_at'
    ]
    list_filter = ['status', 'payment_method__payment_type', 'created_at']
    search_fields = ['payment__payment_id', 'payment_method__name', 'external_transaction_id']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def payment_link(self, obj):
        url = reverse('admin:payment_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_id)
    payment_link.short_description = 'Payment'
    payment_link.admin_order_field = 'payment__payment_id'

    def status_display(self, obj):
        # If obj.status is a string display it, otherwise try color
        try:
            color = obj.status.color if hasattr(obj.status, "color") else "#6c757d"
            status_name = obj.status.name if hasattr(obj.status, "name") else str(obj.status)
        except Exception:
            color, status_name = "#6c757d", str(obj.status)
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color, status_name or 'Unknown'
        )
    status_display.short_description = 'Status'

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'payment_link', 'refund_type', 'refund_reason', 'amount',
        'status_display', 'processed_by', 'created_at'
    ]
    list_filter = [
        'refund_type', 'refund_reason', 'status', 'created_at'
    ]
    search_fields = [
        'payment__payment_id', 'external_refund_id', 'notes'
    ]
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
    ordering = ['-created_at']
    fieldsets = (
        ('Refund Info', {'fields': (
            'payment', 'refund_type', 'refund_reason', 'amount', 'external_refund_id', 'status'
        )}),
        ('Processing', {'fields': ('processed_by', 'processed_at')}),
        ('Notes', {'fields': ('notes',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def payment_link(self, obj):
        url = reverse('admin:payment_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_id)
    payment_link.short_description = 'Payment'
    payment_link.admin_order_field = 'payment__payment_id'

    def status_display(self, obj):
        try:
            color = obj.status.color if hasattr(obj.status, "color") else "#6c757d"
            status_name = obj.status.name if hasattr(obj.status, "name") else str(obj.status)
        except Exception:
            color, status_name = "#6c757d", str(obj.status)
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color, status_name or 'Unknown'
        )
    status_display.short_description = 'Status'

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'payment_link', 'event_type', 'amount', 'created_at', 'created_by'
    ]
    list_filter = ['event_type', 'created_at']
    search_fields = ['payment__payment_id', 'description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def payment_link(self, obj):
        url = reverse('admin:payment_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_id)
    payment_link.short_description = 'Payment'
    payment_link.admin_order_field = 'payment__payment_id'

# Admin site customization
admin.site.site_header = "BookNgon AI - Payment Management"
admin.site.site_title = "Payment Admin"
admin.site.index_title = "Payment Management Administration"

