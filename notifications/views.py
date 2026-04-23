from rest_framework import viewsets, status, decorators
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification, PushDevice
from .serializers import NotificationSerializer, PushDeviceSerializer
from .services import NotificationDispatcher
from webpush.models import SubscriptionInfo, PushInformation, Group
from main.viewsets import BaseViewSet
from .serializers import PushInformationSerializer, PushGroupSerializer, PushSubscriptionSerializer
from main.viewsets import BaseModelViewSet
from django_filters import rest_framework as filters
from staff.permissions import IsBusinessManager, IsBusinessManagerOrReceptionist
from rest_framework.pagination import PageNumberPagination
from main.utils import get_business_managers_group_name
dispatcher = NotificationDispatcher()


class NotificationFilter(filters.FilterSet):
    # This FilterSet allows you to query notifications using filters in the URL.
    # For example: /api/notifications/?business_id=<id>&channel=sms&status=sent
    business_id = filters.UUIDFilter(field_name="business_id", lookup_expr="exact", required=True)
    channel = filters.CharFilter(field_name="channel", lookup_expr="exact")
    status = filters.CharFilter(field_name="status", lookup_expr="exact")

    class Meta:
        model = Notification
        fields = ["channel", "status", "business_id"]

class NotificationViewSet(BaseModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    filterset_class = NotificationFilter
    search_fields = ["to", "title", "body"]
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    pagination_class = PageNumberPagination
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000
    ordering = ["-created_at"]

    def list(self, request, *args, **kwargs):
        self.paginator.page_size = request.query_params.get('page_size', 50)
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        serializer = NotificationSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class PushNotificationFilter(filters.FilterSet):
    business_id = filters.UUIDFilter(field_name="business_id", lookup_expr="exact", required=True)
    channel = filters.CharFilter(field_name="channel", lookup_expr="exact")

    class Meta:
        model = Notification
        fields = ["channel", "business_id"]

class PushNotificationViewSet(BaseModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    search_fields = ["to", "title", "body"]
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = PushNotificationFilter

    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(channel=Notification.Channel.PUSH).order_by("-created_at")
        print("get_queryset:: ", queryset)
        return self.filter_queryset(queryset)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        self.paginator.page_size = request.query_params.get('page_size', 20)
        page = self.paginate_queryset(queryset)
        total_push_notifications = queryset.count()
        PER_PUSH_COST = 0.001 # 1 Push notification per notification
        total_push_cost = total_push_notifications * PER_PUSH_COST
        metadata = {
            "total_notifications": total_push_notifications,
            "total_cost": total_push_cost,
            "per_notification_cost": PER_PUSH_COST,
        }
        if page is not None:
            serializer = NotificationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data, metadata=metadata)
        
        serializer = NotificationSerializer(queryset, many=True)
        return self.response_success(serializer.data, metadata=metadata)

class SMSNotificationFilter(filters.FilterSet):
    
    created_date_from = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_date_to = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    recipient = filters.CharFilter(field_name="to", lookup_expr="icontains")
    business_id = filters.UUIDFilter(field_name="business_id", lookup_expr="exact", required=True)
    
    class Meta:
        model = Notification
        fields = ["status", "created_date_from", "created_date_to", "recipient", "business_id"]

class SMSNotificationViewSet(BaseModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    filterset_class = SMSNotificationFilter
    search_fields = ["to", "title", "body"]
    pagination_class = PageNumberPagination
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000

    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(channel=Notification.Channel.SMS).order_by("-created_at")
        return self.filter_queryset(queryset)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        self.paginator.page_size = request.query_params.get('page_size', 20)
        page = self.paginate_queryset(queryset)
        
        total_sms_notifications = queryset.count()
        PER_SMS_COST = 0.03 # 1 SMS per notification
        total_sms_cost = total_sms_notifications * PER_SMS_COST
        metadata = {
            "total_notifications": total_sms_notifications,
            "total_cost": total_sms_cost,
            "per_notification_cost": PER_SMS_COST,
        }
        if page is not None:
            serializer = NotificationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data, metadata=metadata)
        
        serializer = NotificationSerializer(queryset, many=True)
        return self.response_success(serializer.data, metadata=metadata)

class PushDeviceViewSet(viewsets.ModelViewSet):
    queryset = PushDevice.objects.all().order_by("-created_at")
    serializer_class = PushDeviceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["user", "provider", "active"]
    search_fields = ["token"]


class WebPushViewSet(BaseViewSet):
    queryset = PushInformation.objects.all()
    serializer_class = PushInformationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="subscribe")
    def subscribe(self, request):
        try:
            subscription, created = SubscriptionInfo.objects.update_or_create(
                endpoint=request.data.get("endpoint"),
                auth=request.data.get("auth"),
                defaults={
                    "auth": request.data.get("auth"),
                    "p256dh": request.data.get("p256dh"),
                    "browser": request.data.get("browser"),
                    "user_agent": request.data.get("user_agent"),
                }
            )
         
            user = request.user
            business = user.business
          
            if created:
                if not business:
                    return self.response_error("User is not associated with a business")
                
                if user.role.is_managers():
                    group = Group.objects.filter(name=get_business_managers_group_name(business.id)).first()
                    push_information = PushInformation.objects.create(
                        subscription=subscription,
                        user=user,
                        group=group,
                    )
                else:
                    push_information = PushInformation.objects.create(
                        subscription=subscription,
                        user=user,
                    )
            else:
                push_information = PushInformation.objects.filter(subscription=subscription).first()
                
            serializer = PushInformationSerializer(push_information)
            
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))
    
    @action(detail=False, methods=["post"], url_path="unsubscribe")
    def unsubscribe(self, request):
        try:
            endpoint = request.data.get("endpoint")
            subscription = SubscriptionInfo.objects.filter(endpoint=endpoint).first()
            if subscription:
                PushInformation.objects.filter(subscription=subscription).delete()
                subscription.delete()
                
                return self.response_success(data=None, message="Unsubscribed successfully")
            else:
                return self.response_error(data=None, message="Subscription not found")
        except Exception as e:
            return self.response_error(data=None, message=str(e))
        
