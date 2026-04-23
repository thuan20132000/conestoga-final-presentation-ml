from rest_framework import serializers
from gift.serializers import GiftCardTransactionSerializer
from .models import (
    PaymentMethod, Payment, PaymentDiscount, Refund, PaymentGateway
)
from django.db.models import Sum
from appointment.serializers import AppointmentDetailSerializer


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'name', 'payment_type', 'is_active', 'is_default',
            'processing_fee_percentage', 'processing_fee_fixed',
            'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PaymentGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGateway
        fields = ['id', 'name', 'gateway_type', 'is_active', 'is_default', 'test_mode', 'merchant_id']
        read_only_fields = ['id', 'created_at', 'updated_at']

class PaymentRefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ['id', 'payment', 'amount', 'status', 'created_at', 'updated_at', 'refund_type', 'refund_reason', 'notes']
        read_only_fields = ['created_at', 'updated_at']



class PaymentDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDiscount
        fields = ['id', 'discount_amount', 'discount_percentage', 'discount_code', 'discount_description', 'created_at']
        read_only_fields = ['created_at']
    
class PaymentDiscountCreateSerializer(PaymentDiscountSerializer):
    class Meta(PaymentDiscountSerializer.Meta):
        fields = [
            'discount_amount',
            'discount_percentage',
            'discount_code', 
            'discount_description',
        ]

class PaymentSerializer(serializers.ModelSerializer):
    
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    discounts = PaymentDiscountSerializer(many=True, read_only=True)
    gift_card_redemptions = serializers.SerializerMethodField()
    service_amount = serializers.SerializerMethodField()
    class Meta:
        model = Payment
        fields = [
            'id',
            'payment_method',
            'payment_method_name',
            'business',
            'client',
            'appointment',
            'status',
            'amount',
            'currency',
            'external_transaction_id',
            'processing_fee',
            'net_amount',
            'created_at',
            'updated_at',
            'processed_at',
            'completed_at',
            'processed_by',
            'notes',
            'internal_notes',
            'gift_card_redemptions',
            'discounts',
            'service_amount',
        ]
        read_only_fields = ['created_at', 'updated_at']
        
    def get_gift_card_redemptions(self, obj):
        return GiftCardTransactionSerializer(obj.gift_card_transactions.all(), many=True).data

    def get_service_amount(self, obj):
        if obj.appointment and obj.appointment.appointment_services.exists():
            return obj.appointment.appointment_services.aggregate(Sum('custom_price'))['custom_price__sum']
        return 0

class PaymentCreateSerializer(PaymentSerializer):
    class Meta:
        model = Payment
        fields = [
            'payment_method',
            'business',
            'client',
            'appointment',
            'amount',
            'currency',
            'external_transaction_id',
            'processing_fee',
            'net_amount',
            'notes',
            'internal_notes',
            'status',
        ]


class PaymentDetailSerializer(PaymentSerializer):
    discounts = PaymentDiscountSerializer(many=True, read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    refund = PaymentRefundSerializer(read_only=True)
    appointment = AppointmentDetailSerializer(read_only=True)
    class Meta(PaymentSerializer.Meta):
        model = Payment
        fields = PaymentSerializer.Meta.fields + ['discounts', 'payment_method_name', 'refund', 'appointment']
        read_only_fields = PaymentSerializer.Meta.read_only_fields + ['refund', 'appointment']
        
        

class PaymentRefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ['id', 'payment', 'amount', 'status', 'created_at', 'updated_at', 'refund_type', 'refund_reason', 'notes']
        read_only_fields = ['created_at', 'updated_at']

class PaymentRefundCreateSerializer(PaymentRefundSerializer):
    class Meta(PaymentRefundSerializer.Meta):
        fields = ['payment', 'amount', 'refund_type', 'refund_reason', 'notes']
        
class AppointmentPaymentSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Payment
        fields = [
            'id', 
            'payment_method', 
            'payment_method_name', 
            'payment_method_type', 
            'amount', 
            'currency', 
            'external_transaction_id', 
            'processing_fee',
            'net_amount', 
            'created_at', 
            'updated_at', 
            'processed_at', 
            'completed_at', 
            'processed_by', 
            'notes', 
            'internal_notes', 
            'status'
        ]
        read_only_fields = ['created_at', 'updated_at']