from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid
import secrets
import string


class GiftCardStatusType(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    EXPIRED = "expired", "Expired"
    REDEEMED = "redeemed", "Redeemed"
    CANCELLED = "cancelled", "Cancelled"


class GiftCardTransactionType(models.TextChoices):
    PURCHASE = "purchase", "Purchase"
    REDEMPTION = "redemption", "Redemption"
    REFUND = "refund", "Refund"
    ADJUSTMENT = "adjustment", "Adjustment"
    EXPIRATION = "expiration", "Expiration"


class GiftCard(models.Model):
    """Gift card model for managing gift cards"""
    
    # Unique identifier
    card_code = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Unique gift card code"
    )
    
    # Business relationship
    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='gift_cards',
        help_text="Business that issued the gift card"
    )
    
    # Client relationship (purchaser)
    purchaser = models.ForeignKey(
        'client.Client',
        on_delete=models.SET_NULL,
        related_name='purchased_gift_cards',
        null=True,
        blank=True,
        help_text="Client who purchased the gift card"
    )
    
    # Recipient information (if different from purchaser)
    recipient_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Name of the gift card recipient"
    )
    recipient_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email of the gift card recipient"
    )
    recipient_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Phone number of the gift card recipient"
    )
    
    # Amount and balance
    initial_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Initial amount loaded onto the gift card"
    )
    
    current_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current balance remaining on the gift card"
    )
    
    # Currency
    currency = models.CharField(
        max_length=10,
        choices=[
            ('CAD', 'CAD'),
            ('USD', 'USD'),
            ('EUR', 'EUR'),
            ('GBP', 'GBP'),
            ('JPY', 'JPY'),
            ('AUD', 'AUD'),
            ('NZD', 'NZD'),
        ],
        default='USD',
        help_text="Currency of the gift card"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=GiftCardStatusType.choices,
        default=GiftCardStatusType.ACTIVE,
        help_text="Status of the gift card"
    )
    
    # Dates
    issued_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time the gift card was issued"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiration date of the gift card (null = no expiration)"
    )
    redeemed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time the gift card was fully redeemed"
    )
    
    # Payment reference
    payment = models.ForeignKey(
        'payment.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gift_cards',
        help_text="Payment used to purchase this gift card"
    )
    
    # Notes
    message = models.TextField(
        blank=True,
        null=True,
        help_text="Personal message for the recipient"
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Internal notes about the gift card"
    )
    
    # Is online or offline
    is_online_purchase = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['card_code']),
            models.Index(fields=['business', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"Gift Card {self.card_code} - ${self.current_balance}"
    
    def save(self, *args, **kwargs):
        if not self.card_code:
            self.card_code = self.generate_unique_code()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_unique_code():
        """Generate a unique gift card code"""
        while True:
            # Generate a code: 4 letters + 8 digits (e.g., GIFT12345678)
            letters = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(2))
            digits = ''.join(secrets.choice(string.digits) for _ in range(4))
            code = f"{letters}{digits}"
            
            if not GiftCard.objects.filter(card_code=code).exists():
                return code
    
    @property
    def is_active(self) -> bool:
        """Check if gift card is active and not expired"""
        if self.status != GiftCardStatusType.ACTIVE:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.current_balance <= 0:
            return False
        return True
    
    @property
    def is_expired(self) -> bool:
        """Check if gift card is expired"""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False
    
    @property
    def is_redeemed(self) -> bool:
        """Check if gift card is fully redeemed"""
        return self.current_balance <= 0 or self.status == GiftCardStatusType.REDEEMED
    
    def redeem(self, amount: Decimal, payment=None):
        """Redeem an amount from the gift card"""
        if not self.is_active:
            raise ValueError("Gift card is not active")
        
        if amount > self.current_balance:
            raise ValueError("Insufficient balance")
        
        self.current_balance -= amount
        
        if self.current_balance <= 0:
            self.status = GiftCardStatusType.REDEEMED
            self.redeemed_at = timezone.now()
        
        self.save()
        
        # Create transaction record
        GiftCardTransaction.objects.create(
            gift_card=self,
            transaction_type=GiftCardTransactionType.REDEMPTION,
            amount=amount,
            balance_after=self.current_balance,
            payment=payment,
            description=f"Redeemed ${amount} from gift card"
        )
        
        return self.current_balance


class GiftCardTransaction(models.Model):
    """Transaction history for gift cards"""
    
    gift_card = models.ForeignKey(
        GiftCard,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text="Gift card this transaction belongs to"
    )
    
    transaction_type = models.CharField(
        max_length=20,
        choices=GiftCardTransactionType.choices,
        help_text="Type of transaction"
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Amount of the transaction"
    )
    
    balance_before = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Balance before this transaction"
    )
    
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Balance after this transaction"
    )
    
    payment = models.ForeignKey(
        'payment.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gift_card_transactions',
        help_text="Payment associated with this transaction"
    )
    
    appointment = models.ForeignKey(
        'appointment.Appointment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gift_card_transactions',
        help_text="Appointment where gift card was used"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of the transaction"
    )
    
    created_by = models.ForeignKey(
        'staff.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gift_card_transactions',
        help_text="Staff member who created this transaction"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gift_card', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - ${self.amount} - {self.gift_card.card_code}"
