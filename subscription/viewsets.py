from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from main.viewsets import BaseModelViewSet
from staff.permissions import IsBusinessManager
from .models import SubscriptionPlan, BusinessSubscription
from .serializers import (
    SubscriptionPlanSerializer,
    BusinessSubscriptionSerializer,
    BusinessSubscriptionCreateSerializer,
    CancelSubscriptionSerializer,
    ChangePlanSerializer,
)
from .services import SubscriptionService
from business.models import Business

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class SubscriptionPlanViewSet(BaseModelViewSet):
    """Read-only viewset listing active subscription plans."""
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]
    http_method_names = ['get', 'head', 'options']

    def list(self, request, *args, **kwargs):
        plans = self.get_queryset()
        serializer = self.get_serializer(plans, many=True)
        return self.response_success(serializer.data, message="Plans retrieved successfully")
    


class BusinessSubscriptionViewSet(BaseModelViewSet):
    """ViewSet for managing a business's subscription."""
    queryset = BusinessSubscription.objects.select_related('plan', 'business')
    serializer_class = BusinessSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsBusinessManager]
    http_method_names = ['get', 'post', 'head', 'options']

    def _get_business(self, request):
        business_id = request.query_params.get('business_id')
        if not business_id:
            return None, self.response_error(
                message="business_id query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            return None, self.response_error(
                message="Business not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return business, None

    @action(detail=False, methods=['get'], url_path='my-subscription')
    def my_subscription(self, request):
        business, err = self._get_business(request)
        if err:
            return err

        try:
            sub = BusinessSubscription.objects.select_related('plan').get(business=business)
        except BusinessSubscription.DoesNotExist:
            return self.response_success(None, message="No subscription found for this business.")

        serializer = BusinessSubscriptionSerializer(sub)
        return self.response_success(serializer.data, message="Subscription retrieved successfully.")

    @action(detail=False, methods=['post'], url_path='subscribe')
    def subscribe(self, request):
        business, err = self._get_business(request)
        if err:
            return err

        serializer = BusinessSubscriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.response_error(serializer.errors)

        try:
            checkout_url = SubscriptionService().create_subscription(
                business=business,
                plan_id=serializer.validated_data['plan_id'],
                billing_cycle=serializer.validated_data['billing_cycle'],
                success_url=serializer.validated_data['success_url'],
                cancel_url=serializer.validated_data['cancel_url'],
            )
        except Exception as e:
            logger.error("subscribe error: %s", e)
            return self.response_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        return self.response_success(
            {'checkout_url': checkout_url},
            status_code=status.HTTP_201_CREATED,
            message="Redirect user to checkout_url to complete subscription.",
        )

    @action(detail=False, methods=['post'], url_path='cancel')
    def cancel(self, request):
        business, err = self._get_business(request)
        if err:
            return err

        try:
            sub = BusinessSubscription.objects.get(business=business)
        except BusinessSubscription.DoesNotExist:
            return self.response_error(message="No active subscription found.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = CancelSubscriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return self.response_error(serializer.errors)

        try:
            print("================= Cancel Subscription service:: ", sub)
            sub = SubscriptionService().cancel_subscription(
                business_subscription=sub,
                immediate=serializer.validated_data.get('immediate', False),
            )
        except Exception as e:
            logger.error("cancel error: %s", e)
            return self.response_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        return self.response_success(
            BusinessSubscriptionSerializer(sub).data,
            message="Subscription cancelled successfully.",
        )

    @action(detail=False, methods=['post'], url_path='change-plan')
    def change_plan(self, request):
        business, err = self._get_business(request)
        if err:
            return err

        try:
            sub = BusinessSubscription.objects.get(business=business)
        except BusinessSubscription.DoesNotExist:
            return self.response_error(message="No active subscription found.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = ChangePlanSerializer(data=request.data)
        if not serializer.is_valid():
            return self.response_error(serializer.errors)

        try:
            sub = SubscriptionService().change_plan(
                business_subscription=sub,
                new_plan_id=serializer.validated_data['new_plan_id'],
                new_billing_cycle=serializer.validated_data['new_billing_cycle'],
            )
        except Exception as e:
            logger.error("change_plan error: %s", e)
            return self.response_error(message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

        return self.response_success(
            BusinessSubscriptionSerializer(sub).data,
            message="Subscription plan changed successfully.",
        )
