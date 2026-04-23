from payment.models import Payment, PaymentStatusType
from django.db import transaction
from django.db import transaction
from typing import TypedDict, Optional, Any
from payment.models import PaymentMethod, PaymentDiscount
from appointment.models import Appointment, AppointmentStatusType, AppointmentService
from django.utils import timezone
from business.models import Business
from django.db.models import Sum, Count
from datetime import datetime
from gift.models import GiftCardTransaction
from gift.services import GiftCardService
from notifications.services import EmailService
import logging

logger = logging.getLogger(__name__)

class CreatePaymentData(TypedDict):
    payment_method_id: int
    business_id: int
    client_id: int
    appointment_id: int
    amount: float
    currency: str
    external_transaction_id: str
    metadata: dict[str, Any]


class PaymentStatsResponse(TypedDict):
    results: list[Payment]
    metadata: dict[str, int | float]


class PaymentService:
    def create_payment(
        self,
        payment_data: CreatePaymentData,
        discounts: list[PaymentDiscount] = None,
        appointment_services: list[AppointmentService] = None,
        metadata: dict[str, Any] = None
    ) -> Payment:
        try:
            with transaction.atomic():
                # create appointment services
                if appointment_services:
                    for appointment_service in appointment_services:
                        appointment_service_obj, created = AppointmentService.objects.update_or_create(
                            id=appointment_service['id'],
                            defaults={
                                'service_id': appointment_service['service'],
                                'staff_id': appointment_service['staff'],
                                'is_staff_request': appointment_service['is_staff_request'],
                                'start_at': appointment_service['start_at'],
                                'end_at': appointment_service['end_at'],
                                'custom_price': appointment_service['custom_price'] or 0,
                                'tip_amount': appointment_service['tip_amount'] or 0,
                                'appointment_id': appointment_service['appointment'],
                            }
                        )
                payment = Payment.objects.create(**payment_data)
                # create payment discounts
                if discounts:
                    for discount in discounts:
                        payment_discount = PaymentDiscount.objects.create(
                            payment=payment,
                            discount_amount=discount.get('discount_amount', 0),
                            discount_percentage=discount.get(
                                'discount_percentage', 0),
                            discount_code=discount.get('discount_code', ''),
                            discount_description=discount.get(
                                'discount_description', '')
                        )
                        print("payment_discount:: ", payment_discount.__dict__)

                if payment.status == PaymentStatusType.COMPLETED:
                    appointment = payment.appointment
                    appointment.payment_status = payment.status
                    appointment.status = AppointmentStatusType.CHECKED_OUT
                    appointment.metadata = metadata or {}
                    appointment.save()

                if payment.status == PaymentStatusType.PENDING:
                    appointment = payment.appointment
                    appointment.payment_status = payment.status
                    appointment.status = AppointmentStatusType.PENDING_PAYMENT
                    appointment.save()

                return payment
        except Exception as e:
            raise Exception(f"Error creating payment: {e}")

    def process_payment(self, payment: Payment) -> Payment:
        payment.status = PaymentStatusType.COMPLETED
        payment.save()
        return payment

    def refund_payment(self, payment: Payment) -> Payment:
        payment.status = PaymentStatusType.REFUNDED
        payment.save()
        return payment

    def cancel_payment(self, payment: Payment) -> Payment:
        payment.status = PaymentStatusType.CANCELLED
        payment.save()
        return payment

    def update_payment(self, payment: Payment) -> Payment:
        payment.save()
        return payment

    def send_receipt(self, payment: Payment, custom_email: str = None) -> bool:
        client = payment.appointment.client
        if not client or not client.email and not custom_email:
            return False
        appointment = payment.appointment
        services = []
        if appointment:
            for appt_service in appointment.appointment_services.select_related('service', 'staff').all():
                services.append({
                    'service_name': appt_service.service.name if appt_service.service else 'Service',
                    'staff_name': appt_service.staff.get_full_name() if appt_service.staff else '',
                    'price': appt_service.custom_price or (appt_service.service.price if appt_service.service else 0),
                })

        context = {
            'client_name': f"{client.first_name} {client.last_name or ''}".strip(),
            'business_name': payment.business.name if payment.business else '',
            'appointment_date': appointment.appointment_date.strftime('%B %d, %Y') if appointment and appointment.appointment_date else '',
            'payment_method_name': payment.payment_method.name if payment.payment_method else payment.payment_method_type,
            'payment_id': str(payment.payment_id),
            'services': services,
            'total': payment.amount,
            'currency': payment.currency,
            'processing_fee': payment.processing_fee,
            'business_phone': payment.business.phone_number if payment.business else '',
            'business_address': payment.business.address if payment.business else '',
        }

        print("context:: ", context)
        EmailService().send_async(
            subject=f"Your receipt from {context['business_name']}",
            to_email=custom_email or client.email,
            template='emails/payment_receipt.html',
            context=context,
        )
        return True

    def get_payment(self, payment_id: int) -> Payment:
        return Payment.objects.get(id=payment_id)

    def get_payment_stats(self, business: Business, from_date: datetime, to_date: datetime) -> PaymentStatsResponse:
        try:

            current_timezone = timezone.get_current_timezone()

            if from_date and to_date:
                current_timezone = timezone.get_current_timezone()
                timezone_from_date = datetime.strptime(
                    from_date, '%Y-%m-%d').astimezone(current_timezone)
                timezone_to_date = datetime.strptime(
                    to_date, '%Y-%m-%d').astimezone(current_timezone)

                payment_stats = Payment.objects.filter(
                    business=business,
                    created_at__date__range=(timezone_from_date.date(), timezone_to_date.date()),
                    # status=PaymentStatusType.COMPLETED
                )

            else:
                current_timezone = timezone.get_current_timezone()
                timezone_now = timezone.now().astimezone(current_timezone)
                payment_stats = Payment.objects.filter(
                    business=business,
                    created_at__date=timezone_now.date(),
                    # status=PaymentStatusType.COMPLETED
                )

            results = payment_stats.all()
            total_payments = payment_stats.count()
            total_amount = payment_stats.aggregate(
                total=Sum('amount'))['total'] or 0
            total_processing_fees = payment_stats.aggregate(
                total=Sum('processing_fee'))['total'] or 0
            total_net_amount = payment_stats.aggregate(
                total=Sum('net_amount'))['total'] or 0
            total_completed_payments = payment_stats.filter(
                status=PaymentStatusType.COMPLETED).count()
            total_completed_amount = payment_stats.filter(
                status=PaymentStatusType.COMPLETED).aggregate(total=Sum('amount'))['total'] or 0
            total_pending_payments = payment_stats.filter(
                status=PaymentStatusType.PENDING).count()
            total_pending_amount = payment_stats.filter(
                status=PaymentStatusType.PENDING).aggregate(total=Sum('amount'))['total'] or 0
            total_failed_payments = payment_stats.filter(
                status=PaymentStatusType.FAILED).count()
            total_failed_amount = payment_stats.filter(
                status=PaymentStatusType.FAILED).aggregate(total=Sum('amount'))['total'] or 0
            total_refunded_payments = payment_stats.filter(
                status=PaymentStatusType.REFUNDED).count()
            total_refunded_amount = payment_stats.filter(
                status=PaymentStatusType.REFUNDED).aggregate(total=Sum('amount'))['total'] or 0

            total_cash_payments = payment_stats.filter(
                payment_method__name='Cash').count()
            total_credit_card_payments = payment_stats.filter(
                payment_method__name='Credit Card').count()
            total_debit_card_payments = payment_stats.filter(
                payment_method__name='Debit Card').count()
            total_bank_transfer_payments = payment_stats.filter(
                payment_method__name='Bank Transfer').count()
            total_cheque_payments = payment_stats.filter(
                payment_method__name='Cheque').count()
            total_other_payments = payment_stats.filter(
                payment_method__name='Other').count()

            response_data = {
                'total_payments': total_payments,
                'total_amount': total_amount,
                'total_processing_fees': total_processing_fees,
                'total_net_amount': total_net_amount,
                'total_completed_payments': total_completed_payments,
                'total_pending_payments': total_pending_payments,
                'total_failed_payments': total_failed_payments,
                'total_refunded_payments': total_refunded_payments,
                'total_cash_payments': total_cash_payments,
                'total_credit_card_payments': total_credit_card_payments,
                'total_debit_card_payments': total_debit_card_payments,
                'total_bank_transfer_payments': total_bank_transfer_payments,
                'total_cheque_payments': total_cheque_payments,
                'total_other_payments': total_other_payments,
                'total_completed_amount': total_completed_amount,
                'total_pending_amount': total_pending_amount,
                'total_failed_amount': total_failed_amount,
                'total_refunded_amount': total_refunded_amount,
            }

            return PaymentStatsResponse(
                results=results,
                metadata=response_data
            )

        except Exception as e:
            raise Exception(f"Error getting payment stats: {e}")


class POSPaymentService:
    def create_appointment_and_payment(
        self,
        payment_data: dict[str, Any],
        appointment_data: dict[str, Any],
        appointment_services: list[AppointmentService] = None,
        discounts: list[PaymentDiscount] = None,
        gift_card_redemptions: list[GiftCardTransaction] = None,
    ) -> dict[str, Any]:
        try:
            with transaction.atomic():
                
                metadata = appointment_data['metadata'] or {}
                # create appointment
                appointment = Appointment.objects.create(
                    business_id=appointment_data['business'],
                    client_id=appointment_data['client'],
                    appointment_date=appointment_data['appointment_date'],
                    booking_source=appointment_data['booking_source'],
                    start_at=appointment_data['start_at'],
                    end_at=appointment_data['end_at'],
                    payment_status=payment_data['status'],
                    metadata=metadata,
                )
                
                


                # # create appointment services
                if appointment_services:
                    for appointment_service in appointment_services:
                        appointment_service_obj = AppointmentService.objects.create(
                            appointment=appointment,
                            service_id=appointment_service['service'] or None,
                            staff_id=appointment_service['staff'] or None,
                            is_staff_request=appointment_service['is_staff_request'],
                            start_at=appointment_service['start_at'],
                            end_at=appointment_service['end_at'],
                            custom_price=appointment_service['custom_price'] or 0,
                            tip_amount=appointment_service['tip_amount'] or 0,
                            tip_method=appointment_service['tip_method'] or None,
                            metadata=metadata,
                        )



                payment = Payment.objects.create(
                    payment_method_id=payment_data['payment_method'],
                    payment_method_type=payment_data['payment_method_type'],
                    business_id=payment_data['business'],
                    amount=payment_data['amount'],
                    currency=payment_data['currency'],
                    processing_fee=payment_data['processing_fee'],
                    status=payment_data['status'],
                    appointment_id=appointment.id,
                )


                # create payment discounts
                if discounts:
                    for discount in discounts:
                        payment_discount = PaymentDiscount.objects.create(
                            payment=payment,
                            discount_amount=discount.get('discount_amount', 0),
                            discount_percentage=discount.get(
                                'discount_percentage', 0),
                            discount_code=discount.get('discount_code', ''),
                            discount_description=discount.get(
                                'discount_description', '')
                        )

                # create gift card transactions
                if gift_card_redemptions and len(gift_card_redemptions) > 0:

                    if payment.status == PaymentStatusType.COMPLETED:
                        service = GiftCardService()

                        for gift_card_redemption in gift_card_redemptions:
                            result = service.redeem_gift_card(
                                card_code=gift_card_redemption['card_code'],
                                amount=gift_card_redemption['amount'],
                                payment_id=payment.id,
                                appointment_id=appointment.id,
                                description=gift_card_redemption['description'],
                            )
                            print("gift_card_redemption result:: ", result)

                if payment.status == PaymentStatusType.COMPLETED:
                    appointment.payment_status = payment.status
                    appointment.status = AppointmentStatusType.CHECKED_OUT
                    appointment.metadata = metadata
                    appointment.save()

                if payment.status == PaymentStatusType.PENDING:
                    appointment.payment_status = payment.status
                    appointment.status = AppointmentStatusType.PENDING_PAYMENT
                    appointment.save()

                return appointment
        except Exception as e:
            print("error creating appointment and payment", e)
            raise Exception(f"Error creating payment: {e}")

    def update_appointment_and_payment(
        self,
        appointment: Appointment,
        appointment_data: dict[str, Any],
        payment_data: dict[str, Any],
        discounts: list[PaymentDiscount] = None,
        appointment_services: list[AppointmentService] = None,
        gift_card_redemptions: list[GiftCardTransaction] = None,
        metadata: dict[str, Any] = None
    ) -> dict[str, Any]:
        try:
            with transaction.atomic():
             

                metadata = appointment_data.get('metadata', appointment.metadata) or {}
                # update appointment
                appointment.client_id = appointment_data['client']
                appointment.appointment_date = appointment_data['appointment_date']
                appointment.booking_source = appointment_data['booking_source']
                appointment.start_at = appointment_data['start_at']
                appointment.end_at = appointment_data['end_at']
                appointment.save()

                # update appointment services
                if appointment_services:
                    for appointment_service in appointment_services:
                        custom_price = appointment_service['custom_price'] or appointment_service['service_price']
                        appointment_service_obj, created = AppointmentService.objects.update_or_create(
                            id=appointment_service['id'],
                            appointment_id=appointment.id,
                            defaults={
                                'service_id': appointment_service['service'] or None,
                                'staff_id': appointment_service['staff'] or None,
                                'is_staff_request': appointment_service['is_staff_request'],
                                'start_at': appointment_service['start_at'],
                                'end_at': appointment_service['end_at'],
                                'custom_price': custom_price,
                                'tip_amount': appointment_service['tip_amount'] or 0,
                                'appointment_id': appointment.id,
                                'metadata': metadata,
                            }
                        )
                # update payment
                payment = Payment.objects.create(
                    payment_method_id=payment_data['payment_method'],
                    payment_method_type=payment_data['payment_method_type'],
                    business_id=payment_data['business'],
                    amount=payment_data['amount'],
                    currency=payment_data['currency'],
                    processing_fee=payment_data['processing_fee'],
                    status=payment_data['status'],
                    appointment_id=appointment.id,
                )

                if payment.status == PaymentStatusType.COMPLETED:
                    appointment.payment_status = payment.status
                    appointment.status = AppointmentStatusType.CHECKED_OUT
                    appointment.metadata = metadata or {}
                    # create gift card transactions
                    if len(gift_card_redemptions) > 0:

                        service = GiftCardService()

                        for gift_card_redemption in gift_card_redemptions:
                            service.redeem_gift_card(
                                card_code=gift_card_redemption['card_code'],
                                amount=gift_card_redemption['amount'],
                                payment_id=payment.id,
                                appointment_id=appointment.id,
                                description=gift_card_redemption['description'],
                            )

                    appointment.save()

                if payment.status == PaymentStatusType.PENDING:
                    appointment.payment_status = payment.status
                    appointment.status = AppointmentStatusType.PENDING_PAYMENT
                    appointment.save()

                return appointment

        except Exception as e:
            print("error updating appointment and payment:: ", e)
            raise Exception(f"Error updating payment: {e}")
