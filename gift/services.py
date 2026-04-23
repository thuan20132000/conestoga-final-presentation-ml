from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime
from .models import GiftCard, GiftCardTransaction, GiftCardStatusType, GiftCardTransactionType
from payment.models import (
    Payment,
    PaymentStatusType,
    PaymentMethod,
    PaymentMethodType,
)
from payment.stripe_service import StripeService
from business.models import Business
from main.common_settings import ONLINE_BOOKING_URL
from main.utils import money_quantize, get_business_managers_group_name
from notifications.services import EmailService, NotificationDispatcher
from notifications.models import Notification
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class GiftCardService:
    """Service for managing gift card operations"""
    
    def create_gift_card(
        self,
        business_id: int,
        initial_amount: Decimal,
        currency: str = 'USD',
        purchaser_id: Optional[int] = None,
        recipient_name: Optional[str] = None,
        recipient_email: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        expires_at: Optional[timezone.datetime] = None,
        message: Optional[str] = None,
        notes: Optional[str] = None,
        payment_id: Optional[int] = None,
        is_online_purchase: Optional[bool] = False,
    ) -> GiftCard:
        """Create a new gift card"""
        with transaction.atomic():
            gift_card = GiftCard.objects.create(
                business_id=business_id,
                purchaser_id=purchaser_id,
                recipient_name=recipient_name,
                recipient_email=recipient_email,
                recipient_phone=recipient_phone,
                initial_amount=initial_amount,
                current_balance=initial_amount,
                currency=currency,
                expires_at=expires_at,
                message=message,
                notes=notes,
                payment_id=payment_id,
                is_online_purchase=is_online_purchase,
            )
            
            # Create purchase transaction
            GiftCardTransaction.objects.create(
                gift_card=gift_card,
                transaction_type=GiftCardTransactionType.PURCHASE,
                amount=initial_amount,
                balance_before=Decimal('0.00'),
                balance_after=initial_amount,
                payment_id=payment_id,
                description=f"Gift card purchased for ${initial_amount}"
            )
            
            return gift_card
    
    def redeem_gift_card(
        self,
        card_code: str,
        amount: Decimal,
        payment_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        description: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Redeem an amount from a gift card"""
        with transaction.atomic():
            try:
                gift_card = GiftCard.objects.select_for_update().get(card_code=card_code)
            except GiftCard.DoesNotExist:
                raise ValueError("Gift card not found")
            
            if not gift_card.is_active:
                if gift_card.is_expired:
                    raise ValueError("Gift card has expired")
                elif gift_card.status == GiftCardStatusType.REDEEMED:
                    raise ValueError("Gift card has been fully redeemed")
                else:
                    raise ValueError("Gift card is not active")
            amount = money_quantize(amount)
            current_balance = money_quantize(gift_card.current_balance)
            if amount > current_balance:
                raise ValueError(
                    f"Insufficient balance. Available: ${current_balance}, "
                    f"Requested: ${amount}"
                )
            
            balance_before = gift_card.current_balance
            gift_card.current_balance -= amount
            
            if gift_card.current_balance <= 0:
                gift_card.status = GiftCardStatusType.REDEEMED
                gift_card.redeemed_at = timezone.now()
                
            
            gift_card.save()
            
            # Create redemption transaction
            transaction_obj = GiftCardTransaction.objects.create(
                gift_card=gift_card,
                transaction_type=GiftCardTransactionType.REDEMPTION,
                amount=amount,
                balance_before=balance_before,
                balance_after=current_balance,
                payment_id=payment_id,
                appointment_id=appointment_id,
                description=description or f"Redeemed ${amount} from gift card",
                created_by_id=created_by_id,
            )
            
            return {
                'gift_card': gift_card,
                'transaction': transaction_obj,
                'remaining_balance': gift_card.current_balance,
            }
    
    def validate_gift_card(self, card_code: str) -> GiftCard:
        """Validate a gift card code"""
        try:
            gift_card = GiftCard.objects.get(card_code=card_code)
        except GiftCard.DoesNotExist:
            raise ValueError("Gift card not found")
        
        if not gift_card.is_active:
            if gift_card.is_expired:
                raise ValueError("Gift card has expired")
            elif gift_card.status == GiftCardStatusType.REDEEMED:
                raise ValueError("Gift card has been fully redeemed")
            else:
                raise ValueError("Gift card is not active")
        
        return gift_card
    
    def refund_gift_card(
        self,
        gift_card_id: int,
        amount: Decimal,
        refund_payment_id: Optional[int] = None,
        description: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Refund an amount to a gift card"""
        with transaction.atomic():
            try:
                gift_card = GiftCard.objects.select_for_update().get(id=gift_card_id)
            except GiftCard.DoesNotExist:
                raise ValueError("Gift card not found")
            
            if gift_card.status == GiftCardStatusType.CANCELLED:
                raise ValueError("Cannot refund to a cancelled gift card")
            
            # Reactivate if needed
            if gift_card.status == GiftCardStatusType.REDEEMED:
                gift_card.status = GiftCardStatusType.ACTIVE
                gift_card.redeemed_at = None
            
            balance_before = gift_card.current_balance
            gift_card.current_balance += amount
            
            # Ensure balance doesn't exceed initial amount (unless business allows it)
            if gift_card.current_balance > gift_card.initial_amount:
                gift_card.initial_amount = gift_card.current_balance
            
            gift_card.save()
            
            # Create refund transaction
            transaction_obj = GiftCardTransaction.objects.create(
                gift_card=gift_card,
                transaction_type=GiftCardTransactionType.REFUND,
                amount=amount,
                balance_before=balance_before,
                balance_after=gift_card.current_balance,
                payment_id=refund_payment_id,
                description=description or f"Refunded ${amount} to gift card",
                created_by_id=created_by_id,
            )
            
            return {
                'gift_card': gift_card,
                'transaction': transaction_obj,
                'new_balance': gift_card.current_balance,
            }
    
    def cancel_gift_card(
        self,
        gift_card_id: int,
        reason: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> GiftCard:
        """Cancel a gift card"""
        with transaction.atomic():
            try:
                gift_card = GiftCard.objects.select_for_update().get(id=gift_card_id)
            except GiftCard.DoesNotExist:
                raise ValueError("Gift card not found")
            
            if gift_card.status == GiftCardStatusType.CANCELLED:
                raise ValueError("Gift card is already cancelled")
            
            gift_card.status = GiftCardStatusType.CANCELLED
            gift_card.save()
            
            # Create cancellation transaction
            GiftCardTransaction.objects.create(
                gift_card=gift_card,
                transaction_type=GiftCardTransactionType.ADJUSTMENT,
                amount=Decimal('0.00'),
                balance_before=gift_card.current_balance,
                balance_after=gift_card.current_balance,
                description=f"Gift card cancelled. Reason: {reason or 'No reason provided'}",
                created_by_id=created_by_id,
            )
            
            return gift_card
    
    def adjust_gift_card_balance(
        self,
        gift_card_id: int,
        adjustment_amount: Decimal,
        description: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Adjust gift card balance (for admin adjustments)"""
        with transaction.atomic():
            try:
                gift_card = GiftCard.objects.select_for_update().get(id=gift_card_id)
            except GiftCard.DoesNotExist:
                raise ValueError("Gift card not found")
            
            if gift_card.status == GiftCardStatusType.CANCELLED:
                raise ValueError("Cannot adjust a cancelled gift card")
            
            balance_before = gift_card.current_balance
            gift_card.current_balance += adjustment_amount
            
            if gift_card.current_balance < 0:
                raise ValueError("Balance cannot be negative")
            
            # Reactivate if needed
            if gift_card.status == GiftCardStatusType.REDEEMED and gift_card.current_balance > 0:
                gift_card.status = GiftCardStatusType.ACTIVE
                gift_card.redeemed_at = None
            
            gift_card.save()
            
            # Create adjustment transaction
            transaction_obj = GiftCardTransaction.objects.create(
                gift_card=gift_card,
                transaction_type=GiftCardTransactionType.ADJUSTMENT,
                amount=abs(adjustment_amount),
                balance_before=balance_before,
                balance_after=gift_card.current_balance,
                description=description or f"Balance adjusted by ${adjustment_amount}",
                created_by_id=created_by_id,
            )
            
            return {
                'gift_card': gift_card,
                'transaction': transaction_obj,
                'new_balance': gift_card.current_balance,
            }


class GiftCardOnlinePaymentService:
    """Service for online gift card payments"""
    
    def __init__(self, stripe_service: StripeService):
        self.stripe_service = stripe_service
        
    def handle_stripe_event(self, event: Any) -> None:
        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})
        
        if event_type == "checkout.session.completed":
            self._handle_payment_succeeded(data_object)
        elif event_type == "checkout.session.expired":
            logger.info("checkout.session.expired:: %s", data_object)
            # self._handle_payment_failed(data_object)

    def _send_gift_card_email(self, gift_card: GiftCard) -> None:
        recipient_email = gift_card.recipient_email
        if not recipient_email:
            return

        booking_url = ONLINE_BOOKING_URL
        if gift_card.business_id:
            booking_url = f"{ONLINE_BOOKING_URL}/?business_id={gift_card.business_id}"
        business_name = gift_card.business.name if gift_card.business_id else "our business"
        recipient_name = gift_card.recipient_name or "there"
        subject = f"You've received a gift card from {business_name}"

        expires_at = None
        if gift_card.expires_at:
            expires_at = timezone.localtime(gift_card.expires_at).strftime("%Y-%m-%d")
        email_service = EmailService()
        email_service.send_async(subject, recipient_email, "emails/gift_card.html", {
            "recipient_name": recipient_name,
            "business_name": business_name,
            "code": gift_card.card_code,
            "balance": gift_card.current_balance,
            "currency": gift_card.currency,
            "message": gift_card.message,
            "expires_at": expires_at,
            "booking_url": booking_url,
        })
    
    def _send_gift_card_sms(self, gift_card: GiftCard) -> None:
        recipient_phone = gift_card.recipient_phone
        if not recipient_phone:
            return

        business_id = gift_card.business_id
        business_name = gift_card.business.name if gift_card.business_id else "our business"
        business_twilio_phone_number = gift_card.business.twilio_phone_number
        body = f"Hi {gift_card.recipient_name}, you've received a gift card with code {gift_card.card_code} and balance {gift_card.current_balance} available for use at {business_name}. Redeem this gift card when making payments."
        dispatcher = NotificationDispatcher()
        dispatcher.dispatchAsync(
            channel=Notification.Channel.SMS,
            to=recipient_phone,
            title="Gift Card Received",
            body=body,
            business_id=business_id,
            business_twilio_phone_number=business_twilio_phone_number,
        )

    def _get_online_payment_method(self, business_id: int) -> Optional[PaymentMethod]:
        return (
            PaymentMethod.objects.filter(
                business_id=business_id,
                payment_type=PaymentMethodType.ONLINE,
                is_active=True,
            )
            .order_by("-is_default", "name")
            .first()
        )

    def _calculate_processing_fees(
        self,
        amount: Decimal,
        payment_method: Optional[PaymentMethod],
    ) -> tuple[Decimal, Decimal]:
        if not payment_method:
            return Decimal("0.00"), amount
        percentage_fee = (
            amount * Decimal(payment_method.processing_fee_percentage or 0)
        )
        fixed_fee = Decimal(payment_method.processing_fee_fixed or 0)
        processing_fee = money_quantize(percentage_fee + fixed_fee)
        net_amount = money_quantize(amount - processing_fee)
        return processing_fee, net_amount

    def _get_intent_value(self, payment_intent: Any, key: str, default=None):
        if hasattr(payment_intent, "get"):
            try:
                value = payment_intent.get(key, default)
            except Exception:
                value = default
        else:
            value = default
        if value is None:
            value = getattr(payment_intent, key, default)
        return value

    def _serialize_gateway_response(self, payment_intent: Any) -> dict[str, Any]:
        return {
            "id": self._get_intent_value(payment_intent, "id"),
            "status": self._get_intent_value(payment_intent, "status"),
            "amount": self._get_intent_value(payment_intent, "amount"),
            "currency": self._get_intent_value(payment_intent, "currency"),
        }

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def create_stripe_payment_intent(
        self,
        gift_card_data: Dict[str, Any],
    ) -> dict[str, Any]:
        try:
            with transaction.atomic():
                business: Business = gift_card_data["business"]
                purchaser = gift_card_data.get("purchaser")
                amount = money_quantize(Decimal(gift_card_data["initial_amount"]))
                currency = gift_card_data.get("currency", "USD").upper()

                payment_method = self._get_online_payment_method(business.id)
                processing_fee, net_amount = self._calculate_processing_fees(amount, payment_method)

                payment = Payment.objects.create(
                    business=business,
                    client=purchaser,
                    amount=amount,
                    currency=currency,
                    payment_method=payment_method,
                    payment_method_type=PaymentMethodType.ONLINE,
                    status=PaymentStatusType.PENDING,
                    processing_fee=processing_fee,
                    net_amount=net_amount,
                    notes=gift_card_data.get("notes"),
                    internal_notes="Gift card online purchase",
                )

                metadata = {
                    "gift_card_purchase": "true",
                    "business_id": str(business.id),
                    "payment_id": str(payment.id),
                    "initial_amount": str(amount),
                    "currency": currency,
                    "expires_at": gift_card_data.get("expires_at") or None,
                    "message": gift_card_data.get("message"),
                    "notes": gift_card_data.get("notes"),
                    "recipient_name": gift_card_data.get("recipient_name"),
                    "recipient_email": gift_card_data.get("recipient_email"),
                    "recipient_phone": gift_card_data.get("recipient_phone"),
                    "purchaser_id": str(purchaser.id) if purchaser else None,
                }

                stripe_service = StripeService(business_id=business.id)
                payment_intent = stripe_service.create_payment_intent(
                    amount_cents=int(amount * 100),
                    currency=currency.lower(),
                    metadata=metadata,
                    description="Gift card purchase",
                )

                payment.external_transaction_id = self._get_intent_value(payment_intent, "id")
                payment.gateway_response = self._serialize_gateway_response(payment_intent)
                payment.save(update_fields=["external_transaction_id", "gateway_response", "updated_at"])

                return {
                    "payment": payment,
                    "payment_intent": payment_intent,
                }
        except Exception as e:
            print("create_stripe_payment_intent error:: ", e)
            raise e



    def _get_or_create_payment_from_session(self, session: Any) -> Payment:
        try:
            metadata = session.get("metadata", {})
            payment_id = metadata.get("payment_id")
            payment = None
            if payment_id:
                payment = Payment.objects.filter(id=payment_id).first()
            if not payment:
                payment = Payment.objects.filter(
                    external_transaction_id=session.get("payment_intent")).first()
            if payment:
                return payment
        
            business_id = metadata.get("business_id")
            if not business_id:
                raise ValueError("Missing business_id in Stripe session metadata")
            business = Business.objects.get(id=business_id)

            amount_cents = metadata.get("initial_amount")
            amount = money_quantize(Decimal(amount_cents))
            currency = (metadata.get("currency") or "USD").upper()

            payment_method = self._get_online_payment_method(business.id)
            processing_fee, net_amount = self._calculate_processing_fees(amount, payment_method)

            return Payment.objects.create(
                business=business,
                client_id=metadata.get("purchaser_id"),
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                payment_method_type=PaymentMethodType.ONLINE,
                status=PaymentStatusType.COMPLETED,
                completed_at=timezone.now(),
                processing_fee=processing_fee,
                net_amount=net_amount,
                external_transaction_id=session.get("payment_intent"),
                gateway_response=session,
                internal_notes="Gift card online purchase (webhook created)",
            )
        except Exception as e:
            print("error getting or creating payment from session:: ", e)
            raise e

    def _create_payment_from_intent(self, payment_intent: Any) -> Payment:
        metadata = self._get_intent_value(payment_intent, "metadata", {}) or {}

        business_id = metadata.get("business_id")
        if not business_id:
            raise ValueError("Missing business_id in Stripe metadata")
        business = Business.objects.get(id=business_id)

        amount_cents = self._get_intent_value(payment_intent, "amount") or 0
        amount = money_quantize(Decimal(amount_cents) / 100)
        currency = (self._get_intent_value(payment_intent, "currency") or "USD").upper()

        payment_method = self._get_online_payment_method(business.id)
        processing_fee, net_amount = self._calculate_processing_fees(amount, payment_method)

        return Payment.objects.create(
            business=business,
            client_id=metadata.get("purchaser_id") or None,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            payment_method_type=PaymentMethodType.ONLINE,
            status=PaymentStatusType.COMPLETED,
            completed_at=timezone.now(),
            processing_fee=processing_fee,
            net_amount=net_amount,
            internal_notes="Gift card online purchase (webhook created)",
        )

    def _handle_payment_succeeded(self, session: Any) -> None:
        # logger.debug("checkout.session.completed:: %s", session)
        metadata = session.get("metadata", {})
        
        
        # intent = self.stripe_service.retrieve_payment_intent(session.get("payment_intent"))
        payment = self._get_or_create_payment_from_session(session)
        
        if GiftCard.objects.filter(payment=payment).exists():
            return

        expires_at = self._parse_datetime(metadata.get("expires_at"))
        amount_value = metadata.get("initial_amount") or payment.amount
        amount = money_quantize(Decimal(amount_value))
        currency = (metadata.get("currency") or payment.currency).upper()

        gift_card = GiftCardService().create_gift_card(
            business_id=payment.business_id,
            initial_amount=amount,
            currency=currency,
            purchaser_id=metadata.get("purchaser_id") or payment.client_id,
            recipient_name=metadata.get("recipient_name"),
            recipient_email=metadata.get("recipient_email"),
            recipient_phone=metadata.get("recipient_phone"),
            expires_at=expires_at,
            message=metadata.get("message"),
            notes=metadata.get("notes"),
            payment_id=payment.id,
            is_online_purchase=True,
        )
        
        if metadata.get("recipient_email"):
            self._send_gift_card_email(gift_card)
            
        if metadata.get("recipient_phone"):
            self._send_gift_card_sms(gift_card)
            
         
        notification_dispatcher = NotificationDispatcher()

        notification_dispatcher.dispatchAsync(
            channel=Notification.Channel.PUSH,
            to=None,
            group_name=get_business_managers_group_name(payment.business_id),
            title="🧾 Gift Card Purchased",
            body=f"{gift_card.recipient_name} has purchased a gift card for ${amount} {currency} at {gift_card.business.name} successfully.",
            business_id=payment.business_id,
        )

    def _handle_payment_failed(self, payment_intent: Any) -> None:
        payment = self._get_or_create_payment_from_intent(payment_intent)
        payment.status = PaymentStatusType.FAILED
        last_error = self._get_intent_value(payment_intent, "last_payment_error", {}) or {}
        payment.failure_reason = last_error.get("message")
        payment.gateway_response = self._serialize_gateway_response(payment_intent)
        payment.processed_at = timezone.now()
        payment.save(
            update_fields=[
                "status",
                "failure_reason",
                "gateway_response",
                "processed_at",
                "updated_at",
            ]
        )

