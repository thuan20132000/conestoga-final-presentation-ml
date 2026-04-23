from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    PaymentMethod, Payment, PaymentSplit, 
    Refund, PaymentTransaction, PaymentGateway, PaymentStatusType, PaymentDiscount
)
from .serializers import (
    PaymentMethodSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    PaymentRefundSerializer,
)
from .filters import PaymentMethodFilter
from main.viewsets import BaseModelViewSet
from payment.services import PaymentService, POSPaymentService
from django.db import transaction
from payment.models import RefundTypeType
from appointment.models import Appointment
from appointment.serializers import AppointmentSerializer
from django.utils.translation import gettext as _
class PaymentMethodViewSet(BaseModelViewSet):
    """ViewSet for managing payment methods"""
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PaymentMethodFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'is_active']
    ordering = ['name']
    
    
    def get_queryset(self):
        queryset = super().get_queryset()
        business_id = self.request.query_params.get('business_id')
        if business_id:
            queryset = queryset.filter(business_id=business_id)
        return queryset.select_related('business')
    
    @action(detail=False, methods=['post'])
    def set_default(self, request):
        """Set a payment method as default for a business"""
        payment_method_id = request.data.get('payment_method_id')
        business_id = request.data.get('business_id')
        
        if not payment_method_id or not business_id:
            return Response(
                {'error': _('payment_method_id and business_id are required')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            payment_method = PaymentMethod.objects.get(
                id=payment_method_id, business_id=business_id
            )
            
            # Unset other default payment methods for this business
            PaymentMethod.objects.filter(
                business_id=business_id, is_default=True
            ).update(is_default=False)
            
            # Set this one as default
            payment_method.is_default = True
            payment_method.save()
            
            return Response({'message': _('Default payment method updated')})
            
        except PaymentMethod.DoesNotExist:
            return Response(
                {'error': _('Payment method not found')},
                status=status.HTTP_404_NOT_FOUND
            )



class PaymentViewSet(BaseModelViewSet):
    """ViewSet for managing payments"""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    
    def create(self, request, *args, **kwargs):
        
        try:
            request_data = request.data.copy()
            appointment_services = request_data.get('appointment_services', None)
            discounts = request_data.get('discounts', None)
            metadata = request_data.get('metadata', {})
         
            serializer = PaymentCreateSerializer(data=request_data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            payment_service = PaymentService()
            
            payment = payment_service.create_payment(
                payment_data=validated_data, 
                discounts=discounts,
                appointment_services=appointment_services,
                metadata=metadata
            )
            
            return self.response_success(PaymentSerializer(payment).data)
        except Exception as e:
            print("error creating payment", e)
            return self.response_error(str(e))
        
    @action(detail=True, methods=['post'], url_path='refund')
    def refund(self, request, pk=None):
        """Refund a payment"""
        
        try:
            
            with transaction.atomic():
                payment = self.get_object()
                
                request_data = request.data.copy()
                refund_amount = request_data.get('amount', payment.amount)
                refund_reason = request_data.get('refund_reason', 'Refunded via API')
                refund_type = request_data.get('refund_type', RefundTypeType.FULL)
                refund_notes = request_data.get('notes', 'Refunded via API')
                
                # Use update_or_create to handle existing refunds safely (avoids UNIQUE constraint violation)
                refund, created = Refund.objects.update_or_create(
                    payment=payment,
                    defaults={
                        'amount': refund_amount,
                        'refund_type': refund_type,
                        'refund_reason': refund_reason,
                        'status': PaymentStatusType.REFUNDED,
                        'notes': refund_notes
                    }
                )
                
                payment.status = PaymentStatusType.REFUNDED
                payment_appointment = payment.appointment
                payment_appointment.payment_status = PaymentStatusType.REFUNDED
                payment_appointment.save()
                payment.save()
                
                serializer = PaymentSerializer(payment)
                
                return self.response_success(serializer.data)
            
        except Exception as e:
            print("error refunding payment", e)
            return self.response_error(str(e))
        
    
    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process a payment (simulate payment processing)"""
        payment = self.get_object()
        
        
        if payment.is_completed:
            return Response(
                {'error': _('Payment is already completed')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Simulate payment processing
        payment.external_transaction_id = f"txn_{timezone.now().timestamp()}"
        payment.gateway_response = {
            'status': 'success',
            'transaction_id': payment.external_transaction_id,
            'processed_at': timezone.now().isoformat()
        }
        
        # Set status to completed
        completed_status = PaymentStatusType.COMPLETED
        payment.status = completed_status
        payment.processed_by = request.user.staff if hasattr(request.user, 'staff') else None
        payment.save()
        
        serializer = self.get_serializer(payment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='send-receipt')
    def send_receipt(self, request, pk=None):
        """Send a payment receipt email to the client"""
        payment = self.get_object()
        custom_email = request.data.get('custom_email', None)
        service = PaymentService()
        sent = service.send_receipt(payment, custom_email)
        if not sent:
            return self.response_error(_('Client has no email address on file or custom email is not provided'))
        return self.response_success({'detail': _('Receipt sent successfully')})

    @action(detail=True, methods=['post'])
    def fail_payment(self, request, pk=None):
        """Mark a payment as failed"""
        payment = self.get_object()
        
        if payment.is_completed:
            return Response(
                {'error': _('Cannot fail a completed payment')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        failure_reason = request.data.get('failure_reason', _('Payment processing failed'))
        
        payment.failure_reason = failure_reason
        failed_status = PaymentStatusType.FAILED
        payment.status = failed_status
        payment.processed_by = request.user.staff if hasattr(request.user, 'staff') else None
        payment.save()
        
        serializer = self.get_serializer(payment)
        return Response(serializer.data)
    

class PaymentRefundViewSet(BaseModelViewSet):
    """ViewSet for managing payment refunds"""
    queryset = Refund.objects.all()
    serializer_class = PaymentRefundSerializer
    
class POSPaymentViewSet(BaseModelViewSet):
    """ViewSet for managing POS payments"""
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a payment"""
        try:
            appointment = self.get_object()
            serializer = AppointmentSerializer(appointment).data
            return self.response_success(serializer)
        except Exception as e:
            print("error retrieving appointment", e)
            return self.response_error(str(e))
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update a payment"""
        try:
            appointment = self.get_object()
          
            request_data = request.data.copy()
            appointment_data = request_data.get('appointment', None)
            appointment_services = request_data.get('appointment_services', None)
            discounts = request_data.get('discounts', None)
            gift_card_redemptions = request_data.get('gift_card_redemptions', None)
            pos_payment_service = POSPaymentService()
            pos_payment = pos_payment_service.update_appointment_and_payment(
                appointment=appointment,
                payment_data=request_data,
                appointment_services=appointment_services,
                appointment_data=appointment_data,
                gift_card_redemptions=gift_card_redemptions,
                discounts=discounts,
            )
            serializer = AppointmentSerializer(pos_payment).data
            
            return self.response_success(serializer)
        except Exception as e:
            print("error updating appointment", e)
            return self.response_error(str(e))
        except Exception as e:
            print("error partial updating appointment", e)
            return self.response_error(str(e))
    
    # create a new appointment and payment
    def create(self, request):
        """Create a new appointment and payment"""
        try:
            request_data = request.data.copy()
            appointment_data = request_data.get('appointment', None)
            appointment_services = request_data.get('appointment_services', None)
            discounts = request_data.get('discounts', None)
            gift_card_redemptions = request_data.get('gift_card_redemptions', None)
            pos_payment_service = POSPaymentService()
            
            pos_payment = pos_payment_service.create_appointment_and_payment(
                payment_data=request_data,
                appointment_data=appointment_data,
                appointment_services=appointment_services,
                discounts=discounts,
                gift_card_redemptions=gift_card_redemptions,
            )
            serializer = AppointmentSerializer(pos_payment).data
            return self.response_success(serializer)
        except Exception as e:
            print("error creating appointment and payment", e)
            return self.response_error(str(e))

    @action(detail=True, methods=['patch'], url_path='update-appointment-and-payment')
    def update_appointment_and_payment(self, request, *args, **kwargs):
        """Update an appointment and payment"""
        try:
            print("request.data:: ", request.data)
            appointment = self.get_object()
            print("update appointment:: ", appointment)
            
            request_data = request.data.copy()
            appointment_data = request_data.get('appointment', None)
            appointment_services = request_data.get('appointment_services', None)
            discounts = request_data.get('discounts', None)
            gift_card_redemptions = request_data.get('gift_card_redemptions', None)
            pos_payment_service = POSPaymentService()
            pos_payment = pos_payment_service.update_appointment_and_payment(
                appointment=appointment,
                payment_data=request_data,
                appointment_services=appointment_services,
                appointment_data=appointment_data,
                gift_card_redemptions=gift_card_redemptions,
                discounts=discounts,
            )
            serializer = AppointmentSerializer(pos_payment).data
            
            return self.response_success(serializer)
        except Exception as e:
            print("error updating appointment", e)
            return self.response_error(str(e))