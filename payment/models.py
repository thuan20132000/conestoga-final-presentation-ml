from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid


class PaymentMethodType(models.TextChoices):
    CASH = "cash", "Cash"
    CREDIT_CARD = "credit_card", "Credit Card"
    DEBIT_CARD = "debit_card", "Debit Card"
    BANK_TRANSFER = "bank_transfer", "Bank Transfer"
    ONLINE = "online", "Online Payment"
    GIFT_CARD = "gift_card", "Gift Card"
    STORE_CREDIT = "store_credit", "Store Credit"
    SPLIT_PAYMENT = "split_payment", "Split Payment"
    OTHER = "other", "Other"


class PaymentStatusType(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"
    PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"
    CHARGEBACK = "chargeback", "Chargeback"
    NOT_PAID = "not_paid", "Not Paid"


class TransactionTypeType(models.TextChoices):
    PAYMENT = "payment", "Payment"
    REFUND = "refund", "Refund"
    PARTIAL_REFUND = "partial_refund", "Partial Refund"
    CHARGEBACK = "chargeback", "Chargeback"
    ADJUSTMENT = "adjustment", "Adjustment"


class RefundTypeType(models.TextChoices):
    FULL = "full", "Full Refund"
    PARTIAL = "partial", "Partial Refund"
    CHARGEBACK = "chargeback", "Chargeback"
    OTHER = "other", "Other"


class RefundReasonType(models.TextChoices):
    CLIENT_REQUEST = "client_request", "Client Request"
    SERVICE_ISSUE = "service_issue", "Service Issue"
    CANCELLATION = "cancellation", "Cancellation"
    DUPLICATE_PAYMENT = "duplicate_payment", "Duplicate Payment"
    FRAUD = "fraud", "Fraud"
    CHARGEBACK = "chargeback", "Chargeback"
    OTHER = "other", "Other"


class GatewayTypeType(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    PAYPAL = "paypal", "PayPal"
    SQUARE = "square", "Square"
    MONERIS = "moneris", "Moneris"
    INTERAC = "interac", "Interac"
    CUSTOM = "custom", "Custom"


class CurrencyType(models.TextChoices):
    CAD = "CAD", "Canadian Dollar"
    USD = "USD", "United States Dollar"
    EUR = "EUR", "Euro"
    GBP = "GBP", "British Pound"
    JPY = "JPY", "Japanese Yen"
    AUD = "AUD", "Australian Dollar"
    NZD = "NZD", "New Zealand Dollar"


class PaymentTransactionEventType(models.TextChoices):
    PAYMENT_INITIATED = 'payment_initiated', 'Payment Initiated'
    PAYMENT_PROCESSED = 'payment_processed', 'Payment Processed'
    PAYMENT_COMPLETED = 'payment_completed', 'Payment Completed'
    PAYMENT_FAILED = 'payment_failed', 'Payment Failed'
    REFUND_INITIATED = 'refund_initiated', 'Refund Initiated'
    REFUND_COMPLETED = 'refund_completed', 'Refund Completed'
    CHARGEBACK_RECEIVED = 'chargeback_received', 'Chargeback Received'
    STATUS_CHANGED = 'status_changed', 'Status Changed'


class PaymentMethod(models.Model):
    """Payment method configurations for businesses"""

    business = models.ForeignKey(
        'business.Business', on_delete=models.CASCADE, related_name='payment_methods'
    )
    name = models.CharField(max_length=100)
    payment_type = models.CharField(
        max_length=20, choices=PaymentMethodType.choices
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    processing_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text="Processing fee as decimal (0.025 = 2.5%)"
    )
    processing_fee_fixed = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Fixed processing fee amount"
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.business.name} - {self.name}"

    def save(self, *args, **kwargs):
        if self.is_default:
            PaymentMethod.objects.filter(
                business=self.business, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Main payment model for tracking payments"""

    payment_method_type = models.CharField(
        max_length=20, choices=PaymentMethodType.choices, default=PaymentMethodType.OTHER
    )
    transaction_type = models.CharField(
        max_length=20, choices=TransactionTypeType.choices, default=TransactionTypeType.PAYMENT
    )

    payment_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False)

    business = models.ForeignKey(
        'business.Business', on_delete=models.CASCADE, related_name='payments',
        null=True, blank=True
    )
    client = models.ForeignKey(
        'client.Client', on_delete=models.SET_NULL, related_name='payments',
        null=True, blank=True
    )
    appointment = models.ForeignKey(
        'appointment.Appointment',
        on_delete=models.CASCADE,
        related_name='payments',
        null=True, blank=True
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount of the payment"
    )

    currency = models.CharField(
        max_length=10,
        choices=CurrencyType.choices,
        default=CurrencyType.USD,
        help_text="Currency of the payment"
    )

    external_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="External payment processor transaction ID"
    )

    processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Processing fee amount charged"
    )

    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount after processing fees"
    )
    gateway_response = models.JSONField(
        blank=True,
        null=True,
        help_text="Raw response from payment gateway"
    )

    failure_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for payment failure"
    )

    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes for the payment"
    )

    internal_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Internal notes (not visible to client)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time the payment was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date and time the payment was last updated"
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time the payment was processed"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time the payment was completed"
    )

    processed_by = models.ForeignKey(
        'staff.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Staff member who processed the payment",
        related_name='processed_payments'
    )

    status = models.CharField(
        max_length=20,
        choices=PaymentStatusType.choices,
        default=PaymentStatusType.PENDING,
        help_text="Status of the payment"
    )

    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Payment method used for the payment"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['business', 'created_at']),
            models.Index(fields=['client', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['external_transaction_id']),
        ]

    def __str__(self):
        return f"Payment {self.payment_id} - {self.appointment} - ${self.amount}"

    def save(self, *args, **kwargs):
        # Calculate processing fee
        super().save(*args, **kwargs)

    @property
    def is_completed(self) -> bool:
        return self.status and self.status == PaymentStatusType.COMPLETED

    @property
    def is_pending(self) -> bool:
        return self.status and self.status == PaymentStatusType.PENDING

    @property
    def is_failed(self) -> bool:
        return self.status and self.status == PaymentStatusType.FAILED

    @property
    def is_refunded(self) -> bool:
        return self.status and self.status in [PaymentStatusType.REFUNDED, PaymentStatusType.PARTIALLY_REFUNDED]

class PaymentDiscount(models.Model):
    """Payment discount model"""
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='discounts')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_code = models.CharField(max_length=100, blank=True, null=True)
    discount_description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class PaymentSplit(models.Model):
    """For split payments across multiple payment methods"""

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='splits',
        help_text="Payment that the split belongs to"
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name='payment_splits',
        null=True,
        blank=True,
        help_text="Payment method that the split belongs to"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Amount of the split"
    )
    processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Processing fee of the split"
    )
    net_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Net amount of the split"
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatusType.choices,
        default=PaymentStatusType.PENDING,
        help_text="Status of the split"
    )
    external_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="External transaction ID of the split"
    )
    gateway_response = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Split {self.payment.payment_id} - {self.payment_method.name if self.payment_method else 'N/A'} - ${self.amount}"


class Refund(models.Model):
    """Track refunds for payments"""

    refund_type = models.CharField(
        max_length=20, 
        choices=RefundTypeType.choices,
        default=RefundTypeType.FULL,
        blank=True,
        null=True,
        help_text="Type of refund"
    )
    refund_reason = models.CharField(
        max_length=30, 
        choices=RefundReasonType.choices,
        default=RefundReasonType.OTHER,
        blank=True,
        null=True,
        help_text="Reason for the refund"
                                     )
    payment = models.OneToOneField(
        Payment, 
        on_delete=models.PROTECT,
        related_name='refund',
        help_text="Payment that the refund belongs to"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Amount of the refund"
    )
    external_refund_id = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="External refund ID"
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatusType.choices,
        default=PaymentStatusType.REFUNDED,
        help_text="Status of the refund"
    )
    notes = models.TextField(blank=True, null=True,
                             help_text="Notes for the refund"
                             )
    processed_by = models.ForeignKey(
        'staff.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds',
        help_text="Staff member who processed the refund"
    )
    created_at = models.DateTimeField(auto_now_add=True,
                                      help_text="Date and time the refund was created"
                                      )
    updated_at = models.DateTimeField(auto_now=True,
                                      help_text="Date and time the refund was last updated"
                                      )
    processed_at = models.DateTimeField(null=True, blank=True,
                                        help_text="Date and time the refund was processed"
                                        )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund {self.id} - {self.payment.payment_id} - ${self.amount}"


class PaymentTransaction(models.Model):
    """Detailed transaction log for audit trail"""

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name='transactions',
        help_text="Payment that the transaction belongs to"
    )
    event_type = models.CharField(
        max_length=30, choices=PaymentTransactionEventType.choices,
        help_text="Type of transaction"
    )
    previous_status = models.CharField(
        max_length=20, choices=PaymentStatusType.choices,
        blank=True, null=True,
        help_text="Previous status of the payment"
    )
    new_status = models.CharField(
        max_length=20, choices=PaymentStatusType.choices,
        blank=True, null=True,
        help_text="New status of the payment"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Amount of the transaction"
    )
    description = models.TextField(
        help_text="Description of the transaction"
    )
    metadata = models.JSONField(blank=True, null=True,
                                help_text="Metadata of the transaction"
                                )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'staff.Staff', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Staff member who created the transaction"
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transaction {self.id} - {self.payment.payment_id} - {self.event_type}"


class PaymentGateway(models.Model):
    """Payment gateway configurations"""

    business = models.ForeignKey(
        'business.Business', on_delete=models.CASCADE, related_name='payment_gateways'
    )
    name = models.CharField(max_length=100)
    gateway_type = models.CharField(
        max_length=20,
        choices=GatewayTypeType.choices,
        default=GatewayTypeType.CUSTOM,
        help_text="Type of gateway"
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="API key for the gateway"
    )
    secret_key = models.CharField(max_length=255, blank=True, null=True,
                                  help_text="Secret key for the gateway"
                                  )
    webhook_secret = models.CharField(max_length=255, blank=True, null=True,
                                      help_text="Webhook secret for the gateway"
                                      )
    merchant_id = models.CharField(max_length=100, blank=True, null=True,
                                   help_text="Merchant ID for the gateway"
                                   )

    supports_refunds = models.BooleanField(default=True)
    supports_partial_refunds = models.BooleanField(default=True)
    supports_recurring = models.BooleanField(default=False)
    test_mode = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True,
                                      help_text="Date and time the gateway was created"
                                      )
    updated_at = models.DateTimeField(auto_now=True,
                                      help_text="Date and time the gateway was last updated"
                                      )

    class Meta:
        ordering = ['name']
        unique_together = ['business', 'name']

    def __str__(self):
        return f"{self.business.name} - {self.name}"

    def save(self, *args, **kwargs):
        # Ensure only one default gateway per business
        if self.is_default:
            PaymentGateway.objects.filter(
                business=self.business, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
