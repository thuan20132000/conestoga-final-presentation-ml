from rest_framework import serializers
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import GiftCard, GiftCardTransaction, GiftCardStatusType, GiftCardTransactionType
from decimal import Decimal
from business.models import Business
from client.models import Client
from payment.models import CurrencyType


class GiftCardTransactionSerializer(serializers.ModelSerializer):
    """Serializer for gift card transactions"""
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    
    class Meta:
        model = GiftCardTransaction
        fields = [
            'id', 'gift_card', 'transaction_type', 'transaction_type_display',
            'amount', 'balance_before', 'balance_after', 'payment', 'appointment',
            'description', 'created_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class GiftCardSerializer(serializers.ModelSerializer):
    """Serializer for gift card model"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_redeemed = serializers.BooleanField(read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    purchaser_name = serializers.CharField(source='purchaser.get_full_name', read_only=True)
    transactions = GiftCardTransactionSerializer(many=True, read_only=True)
    is_online_purchase = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = GiftCard
        fields = [
            'id', 'card_code', 'business', 'business_name', 'purchaser', 'purchaser_name',
            'recipient_name', 'recipient_email', 'recipient_phone',
            'initial_amount', 'current_balance', 'currency', 'status', 'status_display',
            'issued_at', 'expires_at', 'redeemed_at', 'payment', 'message', 'notes',
            'is_active', 'is_expired', 'is_redeemed', 'created_at', 'updated_at',
            'transactions', 'is_online_purchase'
        ]
        read_only_fields = ['id', 'card_code', 'created_at', 'updated_at', 'issued_at']


class GiftCardListSerializer(serializers.ModelSerializer):
    """Simplified serializer for gift card lists"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    is_online_purchase = serializers.BooleanField(read_only=True)
    class Meta:
        model = GiftCard
        fields = [
            'id', 'card_code', 'business', 'business_name', 'purchaser',
            'recipient_name', 'initial_amount', 'current_balance', 'currency',
            'status', 'status_display', 'is_active', 'issued_at', 'expires_at', 'is_online_purchase'
        ]


class GiftCardCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new gift cards"""
    
    class Meta:
        model = GiftCard
        fields = [
            'business', 'purchaser', 'recipient_name', 'recipient_email', 'recipient_phone',
            'initial_amount', 'currency', 'expires_at', 'message', 'notes', 'payment'
        ]
    
    def validate_initial_amount(self, value):
        """Validate initial amount"""
        if value <= 0:
            raise serializers.ValidationError(_("Initial amount must be greater than zero"))
        return value
    
    def validate_expires_at(self, value):
        """Validate expiration date"""
        if value and value <= timezone.now():
            raise serializers.ValidationError(_("Expiration date must be in the future"))
        return value


class GiftCardOnlinePaymentIntentSerializer(serializers.Serializer):
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all())
    purchaser = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        required=False,
        allow_null=True,
    )
    recipient_name = serializers.CharField(required=False, allow_blank=True)
    recipient_email = serializers.EmailField(required=False, allow_blank=True)
    recipient_phone = serializers.CharField(required=False, allow_blank=True)
    initial_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.ChoiceField(
        choices=GiftCard._meta.get_field("currency").choices,
        required=False,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_initial_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_("Initial amount must be greater than zero"))
        return value

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError(_("Expiration date must be in the future"))
        return value


class GiftCardRedeemSerializer(serializers.Serializer):
    """Serializer for redeeming gift cards"""
    card_code = serializers.CharField(required=True, help_text="Gift card code to redeem")
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        help_text="Amount to redeem"
    )
    payment_id = serializers.IntegerField(required=False, allow_null=True, help_text="Payment ID if redeeming for a payment")
    appointment_id = serializers.IntegerField(required=False, allow_null=True, help_text="Appointment ID if redeeming for an appointment")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Description of redemption")
    
    def validate_amount(self, value):
        """Validate redemption amount"""
        if value <= 0:
            raise serializers.ValidationError(_("Redemption amount must be greater than zero"))
        return value
    
    def validate(self, data):
        """Validate redemption request"""
        card_code = data.get('card_code')
        amount = data.get('amount')
        
        try:
            gift_card = GiftCard.objects.get(card_code=card_code)
        except GiftCard.DoesNotExist:
            raise serializers.ValidationError({"card_code": _("Gift card not found")})
        
        if not gift_card.is_active:
            raise serializers.ValidationError({"card_code": _("Gift card is not active")})
        
        if amount > gift_card.current_balance:
            raise serializers.ValidationError({
                "amount": _("Insufficient balance. Available balance: ${balance}").format(
                    balance=gift_card.current_balance
                )
            })
        
        data['gift_card'] = gift_card
        return data


class GiftCardValidateSerializer(serializers.Serializer):
    """Serializer for validating gift card codes"""
    card_code = serializers.CharField(required=True, help_text="Gift card code to validate")
    
    def validate(self, data):
        """Validate gift card code"""
        card_code = data.get('card_code')
        
        try:
            gift_card = GiftCard.objects.get(card_code=card_code)
        except GiftCard.DoesNotExist:
            raise serializers.ValidationError({"card_code": _("Gift card not found")})
        
        if not gift_card.is_active:
            if gift_card.is_expired:
                raise serializers.ValidationError({"card_code": _("Gift card has expired")})
            elif gift_card.status == GiftCardStatusType.REDEEMED:
                raise serializers.ValidationError({"card_code": _("Gift card has been fully redeemed")})
            else:
                raise serializers.ValidationError({"card_code": _("Gift card is not active")})
        
        data['gift_card'] = gift_card
        return data


class GiftCardCheckoutSerializer(serializers.Serializer):
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.ChoiceField(choices=CurrencyType.values)
    metadata = serializers.JSONField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    success_url = serializers.URLField(required=False, allow_blank=True)
    cancel_url = serializers.URLField(required=False, allow_blank=True)
    recipient_name = serializers.CharField(required=False, allow_blank=True)
    recipient_email = serializers.EmailField(required=False, allow_blank=True)
    recipient_phone = serializers.CharField(required=False, allow_blank=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_("Amount must be greater than zero"))
        return value
    
    def validate_currency(self, value):
        print("value:: ", value)
        if value not in CurrencyType.values:
            raise serializers.ValidationError(_("Invalid currency"))
        return value
    
    def validate_metadata(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError(_("Metadata must be a dictionary"))
        if "business_id" not in value:
            raise serializers.ValidationError(_("Business ID must be provided"))
        return value
    