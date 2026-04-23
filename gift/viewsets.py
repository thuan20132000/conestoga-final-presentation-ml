from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import GiftCard, GiftCardTransaction, GiftCardStatusType
from .serializers import (
    GiftCardSerializer,
    GiftCardListSerializer,
    GiftCardCreateSerializer,
    GiftCardRedeemSerializer,
    GiftCardValidateSerializer,
    GiftCardTransactionSerializer,
)
from .services import GiftCardService
from main.viewsets import BaseModelViewSet, BaseAPIView
from rest_framework.permissions import IsAuthenticated
from staff.permissions import IsBusinessManager, IsBusinessManagerOrReceptionist

from .services import GiftCardOnlinePaymentService
from payment.stripe_service import StripeService
from rest_framework.permissions import AllowAny
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class GiftCardViewSet(BaseModelViewSet):
    """ViewSet for managing gift cards"""
    queryset = GiftCard.objects.all()
    serializer_class = GiftCardSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['card_code', 'recipient_name', 'recipient_email', 'recipient_phone']
    ordering_fields = ['created_at', 'issued_at', 'expires_at', 'current_balance', 'initial_amount']
    ordering = ['-created_at']
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    
    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == 'list':
            return GiftCardListSerializer
        elif self.action == 'create':
            return GiftCardCreateSerializer
        return GiftCardSerializer
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by business
        business_id = self.request.query_params.get('business_id')
        if business_id:
            queryset = queryset.filter(business_id=business_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if is_active.lower() == 'true':
                queryset = queryset.filter(
                    status=GiftCardStatusType.ACTIVE,
                    current_balance__gt=0
                ).exclude(
                    expires_at__lt=timezone.now()
                )
            else:
                queryset = queryset.exclude(
                    status=GiftCardStatusType.ACTIVE,
                    current_balance__gt=0
                )
        
        # Filter by purchaser
        purchaser_id = self.request.query_params.get('purchaser_id')
        if purchaser_id:
            queryset = queryset.filter(purchaser_id=purchaser_id)
        
        # Filter by card code
        card_code = self.request.query_params.get('card_code')
        if card_code:
            queryset = queryset.filter(card_code__icontains=card_code)
        
        return queryset.select_related('business', 'purchaser', 'payment').prefetch_related('transactions')
    
    def create(self, request, *args, **kwargs):
        """Create a new gift card"""
        try:
            serializer = GiftCardCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            service = GiftCardService()
            gift_card = service.create_gift_card(
                business_id=serializer.validated_data['business'].id,
                initial_amount=serializer.validated_data['initial_amount'],
                currency=serializer.validated_data.get('currency', 'USD'),
                purchaser_id=serializer.validated_data.get('purchaser').id if serializer.validated_data.get('purchaser') else None,
                recipient_name=serializer.validated_data.get('recipient_name'),
                recipient_email=serializer.validated_data.get('recipient_email'),
                recipient_phone=serializer.validated_data.get('recipient_phone'),
                expires_at=serializer.validated_data.get('expires_at'),
                message=serializer.validated_data.get('message'),
                notes=serializer.validated_data.get('notes'),
                payment_id=serializer.validated_data.get('payment').id if serializer.validated_data.get('payment') else None,
            )
            
            return self.response_success(
                GiftCardSerializer(gift_card).data,
                status_code=status.HTTP_201_CREATED,
                message="Gift card created successfully"
            )
        except Exception as e:
            return self.response_error(str(e), status_code=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='redeem')
    def redeem(self, request):
        """Redeem an amount from a gift card"""
        try:
            serializer = GiftCardRedeemSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            gift_card = serializer.validated_data['gift_card']
            amount = serializer.validated_data['amount']
            payment_id = serializer.validated_data.get('payment_id')
            appointment_id = serializer.validated_data.get('appointment_id')
            description = serializer.validated_data.get('description')
            
            service = GiftCardService()
            created_by_id = request.user.staff.id if hasattr(request.user, 'staff') else None
            
            result = service.redeem_gift_card(
                card_code=gift_card.card_code,
                amount=amount,
                payment_id=payment_id,
                appointment_id=appointment_id,
                description=description,
                created_by_id=created_by_id,
            )
            
            return self.response_success(
                {
                    'gift_card': GiftCardSerializer(result['gift_card']).data,
                    'transaction': GiftCardTransactionSerializer(result['transaction']).data,
                    'remaining_balance': float(result['remaining_balance']),
                },
                message="Gift card redeemed successfully"
            )
        except ValueError as e:
            return self.response_error(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.response_error(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='validate')
    def validate_card(self, request):
        """Validate a gift card code"""
        try:
            serializer = GiftCardValidateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            gift_card = serializer.validated_data['gift_card']
            
            return self.response_success(
                GiftCardSerializer(gift_card).data,
                message="Gift card is valid"
            )
        except Exception as e:
            return self.response_error(str(e), status_code=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_card(self, request, pk=None):
        """Cancel a gift card"""
        try:
            reason = request.data.get('reason')
            created_by_id = request.user.staff.id if hasattr(request.user, 'staff') else None
            
            service = GiftCardService()
            gift_card = service.cancel_gift_card(
                gift_card_id=pk,
                reason=reason,
                created_by_id=created_by_id,
            )
            
            return self.response_success(
                GiftCardSerializer(gift_card).data,
                message="Gift card cancelled successfully"
            )
        except ValueError as e:
            return self.response_error(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.response_error(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='refund')
    def refund_to_card(self, request, pk=None):
        """Refund an amount to a gift card"""
        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            refund_payment_id = request.data.get('refund_payment_id')
            description = request.data.get('description')
            created_by_id = request.user.staff.id if hasattr(request.user, 'staff') else None
            
            if amount <= 0:
                return self.response_error(
                    "Amount must be greater than zero",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            service = GiftCardService()
            result = service.refund_gift_card(
                gift_card_id=pk,
                amount=amount,
                refund_payment_id=refund_payment_id,
                description=description,
                created_by_id=created_by_id,
            )
            
            return self.response_success(
                {
                    'gift_card': GiftCardSerializer(result['gift_card']).data,
                    'transaction': GiftCardTransactionSerializer(result['transaction']).data,
                    'new_balance': float(result['new_balance']),
                },
                message="Refund processed successfully"
            )
        except ValueError as e:
            return self.response_error(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.response_error(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='adjust-balance')
    def adjust_balance(self, request, pk=None):
        """Adjust gift card balance (admin only)"""
        try:
            adjustment_amount = Decimal(str(request.data.get('adjustment_amount', 0)))
            description = request.data.get('description')
            created_by_id = request.user.staff.id if hasattr(request.user, 'staff') else None
            
            if adjustment_amount == 0:
                return self.response_error(
                    "Adjustment amount cannot be zero",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            service = GiftCardService()
            result = service.adjust_gift_card_balance(
                gift_card_id=pk,
                adjustment_amount=adjustment_amount,
                description=description,
                created_by_id=created_by_id,
            )
            
            return self.response_success(
                {
                    'gift_card': GiftCardSerializer(result['gift_card']).data,
                    'transaction': GiftCardTransactionSerializer(result['transaction']).data,
                    'new_balance': float(result['new_balance']),
                },
                message="Balance adjusted successfully"
            )
        except ValueError as e:
            return self.response_error(str(e), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.response_error(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Get gift card statistics"""
        try:
            queryset = self.get_queryset()
            business_id = request.query_params.get('business_id')
            
            if business_id:
                queryset = queryset.filter(business_id=business_id)
            
            total_cards = queryset.count()
            active_cards = queryset.filter(
                status=GiftCardStatusType.ACTIVE,
                current_balance__gt=0
            ).exclude(
                Q(expires_at__lt=timezone.now()) & Q(expires_at__isnull=False)
            ).count()
            
            total_issued_value = queryset.aggregate(
                total=Sum('initial_amount')
            )['total'] or Decimal('0.00')
            
            total_outstanding_balance = queryset.filter(
                status=GiftCardStatusType.ACTIVE
            ).aggregate(
                total=Sum('current_balance')
            )['total'] or Decimal('0.00')
            
            redeemed_cards = queryset.filter(
                status=GiftCardStatusType.REDEEMED
            ).count()
            
            expired_cards = queryset.filter(
                expires_at__lt=timezone.now(),
                status=GiftCardStatusType.ACTIVE
            ).count()
            
            return self.response_success({
                'total_cards': total_cards,
                'active_cards': active_cards,
                'redeemed_cards': redeemed_cards,
                'expired_cards': expired_cards,
                'total_issued_value': float(total_issued_value),
                'total_outstanding_balance': float(total_outstanding_balance),
                'total_redeemed_value': float(total_issued_value - total_outstanding_balance),
            })
        except Exception as e:
            return self.response_error(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GiftCardTransactionViewSet(BaseModelViewSet):
    """ViewSet for managing gift card transactions"""
    queryset = GiftCardTransaction.objects.all()
    serializer_class = GiftCardTransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by gift card
        gift_card_id = self.request.query_params.get('gift_card_id')
        if gift_card_id:
            queryset = queryset.filter(gift_card_id=gift_card_id)
        
        # Filter by transaction type
        transaction_type = self.request.query_params.get('transaction_type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by business (through gift card)
        business_id = self.request.query_params.get('business_id')
        if business_id:
            queryset = queryset.filter(gift_card__business_id=business_id)
        
        return queryset.select_related('gift_card', 'payment', 'appointment', 'created_by')




from .serializers import GiftCardCheckoutSerializer
class GiftCardCheckoutViewSet(BaseAPIView):
    """ViewSet for creating checkout sessions for gift cards"""
    
    
    def post(self, request):
        """Create a checkout session"""
        try:
            request_data = request.data.copy()
            serializer = GiftCardCheckoutSerializer(data=request_data)
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            business_id = validated_data.get('business').id
            
            stripe_service = StripeService(business_id=business_id)
            metadata = {
                "business_id": business_id,
                "gift_card_purchase": "true",
                "recipient_name": validated_data.get('recipient_name'),
                "recipient_email": validated_data.get('recipient_email'),
                "recipient_phone": validated_data.get('recipient_phone'),
                "initial_amount": validated_data.get('amount'),
                "currency": validated_data.get('currency'),
                "expires_at": validated_data.get('expires_at'),
                "message": validated_data.get('message'),
                "notes": validated_data.get('notes'),
            }
            
            if validated_data.get('metadata'):
                metadata.update(validated_data.get('metadata'))
            session = stripe_service.create_checkout_session(
                amount_cents=int(Decimal(str(validated_data.get('amount'))) * 100),
                currency=validated_data.get('currency'),
                metadata=metadata,
                description=validated_data.get('description', 'Payment'),
                success_url=validated_data.get('success_url', 'https://example.com/success'),
                cancel_url=validated_data.get('cancel_url', 'https://example.com/cancel'),
            )
            
            return self.response_success({
                "id": session.id,
                "url": session.url,
            })
        except Exception as e:
            print("error creating Gift Card checkout session", e)
            return self.response_error(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    
    def get(self, request):
        """Verify a checkout session"""
        try:
            session_id = request.query_params.get('session_id')
            stripe_service = StripeService()
            session = stripe_service.retrieve_checkout_session(session_id)
            
            return self.response_success(session)
        except Exception as e:
            return self.response_error(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                data=None,
            )