from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q

from .models import Client, ClientPushSubscription
from .serializers import (
    ClientSerializer,
    ClientListSerializer,
    ClientCreateSerializer,
    ClientUpdateSerializer,
    ClientRegisterSerializer,
    ClientGoogleLoginSerializer,
    ClientFacebookLoginSerializer,
    ClientOTPRequestSerializer,
    ClientOTPVerifySerializer,
    ClientTokenRefreshSerializer,
    ClientProfileSerializer,
)
from .authentication import ClientJWTAuthentication
from .permissions import IsClientAuthenticated
from .services import ClientAuthService
from main.viewsets import BaseModelViewSet, BaseAPIView
from appointment.serializers import AppointmentDetailSerializer
from appointment.models import Appointment
from rest_framework.permissions import IsAuthenticated
from staff.permissions import IsBusinessManager, IsBusinessManagerOrReceptionist
from django_filters import rest_framework as filters
from rest_framework.pagination import PageNumberPagination
from webpush.models import SubscriptionInfo, PushInformation, Group


class ClientFilter(filters.FilterSet):
    business_id = filters.UUIDFilter(field_name="primary_business_id", required=True)
    search = filters.CharFilter(
        field_name="search",
        lookup_expr="icontains",
        required=False,
        method="filter_search",
    )
    is_active = filters.BooleanFilter(field_name="is_active", required=False)
    is_vip = filters.BooleanFilter(field_name="is_vip", required=False)

    class Meta:
        model = Client
        fields = ["business_id", "search", "is_active", "is_vip"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
            | Q(email__icontains=value)
            | Q(phone__icontains=value)
            | Q(city__icontains=value)
            | Q(state_province__icontains=value)
            | Q(postal_code__icontains=value)
            | Q(country__icontains=value)
        )

    def filter_is_active(self, queryset, name, value):
        return queryset.filter(is_active=value)

    def filter_is_vip(self, queryset, name, value):
        return queryset.filter(is_vip=value)


class ClientViewSet(BaseModelViewSet):
    """ViewSet for managing clients"""

    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    filterset_class = ClientFilter

    def get_queryset(self):
        """Get queryset for clients"""
        print("self.request.user", self.request.user)
        return self.filter_queryset(super().get_queryset())

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        self.paginator.page_size = request.query_params.get("page_size", 20)
        page = self.paginate_queryset(queryset)

        total_vip_clients = queryset.filter(is_vip=True).count()
        total_clients = queryset.count()

        metadata = {
            "total_vip_clients": total_vip_clients,
            "total_clients": total_clients,
        }

        if page is not None:
            serializer = ClientListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data, metadata=metadata)

        serializer = ClientListSerializer(queryset, many=True)
        return self.response_success(serializer.data, metadata=metadata)

    def create(self, request, *args, **kwargs):
        try:
            serializer = ClientCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            client = serializer.create(serializer.validated_data)
            return self.response_success(ClientSerializer(client).data)
        except Exception as e:
            return self.response_error(str(e))

    def partial_update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = ClientUpdateSerializer(
                instance, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            client = serializer.update(instance, serializer.validated_data)
            return self.response_success(ClientSerializer(client).data)
        except Exception as e:
            return self.response_error(str(e))

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.is_active = False
            instance.save()
            return self.response_success(
                ClientSerializer(instance).data,
                status_code=status.HTTP_200_OK,
                message="Client deleted successfully",
            )
        except Exception as e:
            return self.response_error(str(e), message="Failed to delete client")

    # Get booking history for a client
    @action(detail=True, methods=["get"], url_path="booking-history")
    def booking_history(self, request, pk=None):
        """Get booking history for a client."""
        client = self.get_object()
        clients_appointments = Appointment.objects.filter(
            client=client, is_active=True
        ).order_by("-appointment_date")
        serializer = AppointmentDetailSerializer(clients_appointments, many=True)
        return self.response_success(serializer.data)


# ---- Client Auth Views ----


class ClientRegisterView(BaseAPIView):
    """Register a new client. POST /api/client-auth/register/"""

    def post(self, request):
        serializer = ClientRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success, message, client = ClientAuthService.register(
            first_name=serializer.validated_data["first_name"],
            last_name=serializer.validated_data.get("last_name", ""),
            email=serializer.validated_data.get("email", ""),
            phone=serializer.validated_data.get("phone", ""),
            business_id=serializer.validated_data["business_id"],
        )

        if not success:
            return self.response_error(message=message)

        # Determine which identifier was used for OTP
        email = serializer.validated_data.get("email", "").strip()
        identifier_type = "email" if email else "phone"

        return self.response_success(
            data={
                "client_id": str(client.id),
                "identifier_type": identifier_type,
            },
            message=message,
        )


class ClientGoogleLoginView(BaseAPIView):
    """Login/register client via Google. POST /api/client-auth/google/"""

    def post(self, request):
        serializer = ClientGoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success, data = ClientAuthService.google_login(
            google_id_token=serializer.validated_data["google_id_token"],
            business_id=serializer.validated_data["business_id"],
        )

        if not success:
            return self.response_error(message=data)

        return self.response_success(data=data, message="Login successful.")


class ClientFacebookLoginView(BaseAPIView):
    """Login/register client via Facebook. POST /api/client-auth/facebook/"""

    def post(self, request):
        serializer = ClientFacebookLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success, data = ClientAuthService.facebook_login(
            facebook_access_token=serializer.validated_data["facebook_access_token"],
            business_id=serializer.validated_data["business_id"],
        )

        if not success:
            return self.response_error(message=data)

        return self.response_success(data=data, message="Login successful.")


class ClientRequestOTPView(BaseAPIView):
    """Request OTP for client login. POST /api/client-auth/request-otp/"""

    def post(self, request):
        serializer = ClientOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success, message, client = ClientAuthService.request_otp(
            identifier=serializer.validated_data["identifier"],
            identifier_type=serializer.validated_data["identifier_type"],
            business_id=serializer.validated_data["business_id"],
        )

        if not success:
            return self.response_error(message=message)

        return self.response_success(
            data={"identifier_type": serializer.validated_data["identifier_type"]},
            message=message,
        )


class ClientVerifyOTPView(BaseAPIView):
    """Verify OTP and return JWT tokens. POST /api/client-auth/verify-otp/"""

    def post(self, request):
        serializer = ClientOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success, data = ClientAuthService.verify_otp(
            identifier=serializer.validated_data["identifier"],
            identifier_type=serializer.validated_data["identifier_type"],
            business_id=serializer.validated_data["business_id"],
            code=serializer.validated_data["code"],
        )

        if not success:
            return self.response_error(message=data)

        return self.response_success(data=data, message="Login successful.")


class ClientRefreshTokenView(BaseAPIView):
    """Refresh client access token. POST /api/client-auth/refresh/"""

    def post(self, request):
        serializer = ClientTokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success, data = ClientAuthService.refresh_token(
            refresh_token_str=serializer.validated_data["refresh"],
        )

        if not success:
            return self.response_error(message=data)

        return self.response_success(data=data)


class ClientProfileView(BaseAPIView):
    """Get authenticated client profile. GET /api/client-auth/me/"""

    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClientAuthenticated]

    def get(self, request):
        serializer = ClientProfileSerializer(request.user)
        return self.response_success(data=serializer.data)


# ---- Client Portal Views ----


class ClientAppointmentListView(BaseAPIView):
    """List appointments for authenticated client. GET /api/client-portal/appointments/"""

    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClientAuthenticated]

    def get(self, request):
        appointments = Appointment.objects.filter(
            client=request.user,
            is_active=True,
        ).order_by("-appointment_date")

        paginator = PageNumberPagination()
        paginator.page_size = request.query_params.get("page_size", 20)
        page = paginator.paginate_queryset(appointments, request)

        if page is not None:
            serializer = AppointmentDetailSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = AppointmentDetailSerializer(appointments, many=True)
        return self.response_success(data=serializer.data)


class ClientPushSubscribeView(BaseAPIView):
    """Subscribe client to web push notifications. POST /api/client-portal/push-subscribe/"""

    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClientAuthenticated]

    def post(self, request):
        try:
            client = request.user
            group_name = f"client_{client.id}"

            subscription, _ = SubscriptionInfo.objects.update_or_create(
                endpoint=request.data.get("endpoint"),
                auth=request.data.get("auth"),
                defaults={
                    "auth": request.data.get("auth"),
                    "p256dh": request.data.get("p256dh"),
                    "browser": request.data.get("browser", ""),
                    "user_agent": request.data.get("user_agent", ""),
                },
            )

            group, _ = Group.objects.get_or_create(name=group_name)

            push_info, _ = PushInformation.objects.get_or_create(
                subscription=subscription,
                group=group,
            )

            ClientPushSubscription.objects.get_or_create(
                client=client,
                subscription=subscription,
                push_info=push_info,
            )

            return self.response_success(
                data={"group": group_name},
                message="Push subscription registered.",
            )
        except Exception as e:
            return self.response_error(message=str(e))


class ClientPushUnsubscribeView(BaseAPIView):
    """Unsubscribe client from web push notifications. POST /api/client-portal/push-unsubscribe/"""

    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsClientAuthenticated]

    def post(self, request):
        try:
            endpoint = request.data.get("endpoint")
            subscription = SubscriptionInfo.objects.filter(endpoint=endpoint).first()

            if not subscription:
                return self.response_error(message="Subscription not found.")

            # Clean up related records
            ClientPushSubscription.objects.filter(
                client=request.user, subscription=subscription
            ).delete()
            PushInformation.objects.filter(subscription=subscription).delete()
            subscription.delete()

            return self.response_success(
                data=None, message="Unsubscribed successfully."
            )
        except Exception as e:
            return self.response_error(message=str(e))
