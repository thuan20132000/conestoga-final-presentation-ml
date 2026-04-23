from rest_framework import serializers
from .models import Client, ClientOTP
from django.utils.translation import gettext_lazy as _


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    age = serializers.IntegerField(source="get_age", read_only=True)
    full_address = serializers.CharField(source="get_full_address", read_only=True)
    primary_business_name = serializers.CharField(
        source="primary_business.name", read_only=True
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "date_of_birth",
            "age",
            "address_line1",
            "address_line2",
            "city",
            "state_province",
            "postal_code",
            "country",
            "full_address",
            "emergency_contact_name",
            "emergency_contact_phone",
            "emergency_contact_relation",
            "preferred_contact_method",
            "preferred_language",
            "notes",
            "medical_notes",
            "primary_business",
            "primary_business_name",
            "is_active",
            "is_vip",
            "bonus_time_minutes",
            "minimum_booking_duration_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_email(self, value):
        """Validate email uniqueness"""
        if value:
            queryset = Client.objects.filter(email=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    _("A client with this email already exists.")
                )
        return value

    def validate_phone(self, value):
        """Validate phone uniqueness"""
        if value:
            queryset = Client.objects.filter(phone=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    _("A client with this phone number already exists.")
                )
        return value


class ClientListSerializer(serializers.ModelSerializer):
    """Simplified serializer for client lists"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    age = serializers.IntegerField(source="get_age", read_only=True)
    primary_business_name = serializers.CharField(
        source="primary_business.name", read_only=True
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "date_of_birth",
            "age",
            "primary_business_name",
            "is_active",
            "is_vip",
            "bonus_time_minutes",
            "minimum_booking_duration_minutes",
            "created_at",
            "notes",
        ]


class ClientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new clients"""

    class Meta:
        model = Client
        fields = "__all__"

    def create(self, validated_data):
        """Create client with business"""
        try:
            client = Client.objects.create(**validated_data)
            return client
        except Exception as e:
            raise serializers.ValidationError(str(e))


class ClientUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating existing clients"""

    class Meta:
        model = Client
        fields = "__all__"

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class ClientStatsSerializer(serializers.Serializer):
    """Serializer for client statistics"""

    total_clients = serializers.IntegerField()
    active_clients = serializers.IntegerField()
    vip_clients = serializers.IntegerField()
    new_clients_this_month = serializers.IntegerField()
    clients_by_business = serializers.DictField()
    clients_by_preferred_contact = serializers.DictField()


class BookingClientSerializer(serializers.ModelSerializer):
    """Serializer for booking client"""

    class Meta:
        model = Client
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "preferred_language",
            "primary_business_id",
            "bonus_time_minutes",
            "minimum_booking_duration_minutes",
        ]
        read_only_fields = ["id"]


class BookingClientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a booking client for a specific business"""

    primary_business_id = serializers.UUIDField(required=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Client
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "primary_business_id",
        ]
        read_only_fields = ["id"]

    def update_or_create(self, validated_data):
        """Update or create a client for a specific business"""
        try:

            client = Client.objects.filter(
                primary_business_id=validated_data["primary_business_id"],
                phone=validated_data["phone"],
                is_active=True,
                is_deleted=False,
            ).first()

            if not client:
                client = Client.objects.create(**validated_data)
            else:
                client.first_name = validated_data["first_name"]
                client.last_name = validated_data.get("last_name", None)
                client.email = validated_data.get("email", None)
                client.date_of_birth = validated_data.get("date_of_birth", None)
                client.save()

            return BookingClientSerializer(client).data

        except Exception as e:
            raise serializers.ValidationError(str(e))


# ---- Client Auth Serializers ----


class ClientRegisterSerializer(serializers.Serializer):
    """Validates client self-registration payload."""

    first_name = serializers.CharField(required=True, max_length=100)
    last_name = serializers.CharField(
        required=False, max_length=100, allow_blank=True, default=""
    )
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(
        required=False, max_length=20, allow_blank=True, default=""
    )
    business_id = serializers.UUIDField(required=True)

    def validate(self, attrs):
        email = attrs.get("email", "").strip()
        phone = attrs.get("phone", "").strip()
        if not email and not phone:
            raise serializers.ValidationError(_("Either email or phone is required."))
        return attrs


class ClientGoogleLoginSerializer(serializers.Serializer):
    """Validates Google OAuth login payload."""

    google_id_token = serializers.CharField(required=True)
    business_id = serializers.UUIDField(required=True)


class ClientFacebookLoginSerializer(serializers.Serializer):
    """Validates Facebook OAuth login payload."""

    facebook_access_token = serializers.CharField(required=True)
    business_id = serializers.UUIDField(required=True)


class ClientOTPRequestSerializer(serializers.Serializer):
    """Validates OTP request payload."""

    identifier = serializers.CharField(required=True)
    identifier_type = serializers.ChoiceField(
        choices=[("email", "Email"), ("phone", "Phone")],
        required=True,
    )
    business_id = serializers.UUIDField(required=True)


class ClientOTPVerifySerializer(serializers.Serializer):
    """Validates OTP verification payload."""

    identifier = serializers.CharField(required=True)
    identifier_type = serializers.ChoiceField(
        choices=[("email", "Email"), ("phone", "Phone")],
        required=True,
    )
    business_id = serializers.UUIDField(required=True)
    code = serializers.CharField(required=True, min_length=6, max_length=6)


class ClientTokenRefreshSerializer(serializers.Serializer):
    """Validates client token refresh payload."""

    refresh = serializers.CharField(required=True)


class ClientProfileSerializer(serializers.ModelSerializer):
    """Read-only serializer for client self-view (safe subset of fields)."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    primary_business_name = serializers.CharField(
        source="primary_business.name", read_only=True
    )

    class Meta:
        model = Client
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "date_of_birth",
            "address_line1",
            "address_line2",
            "city",
            "state_province",
            "postal_code",
            "country",
            "preferred_contact_method",
            "preferred_language",
            "primary_business",
            "primary_business_name",
            "is_vip",
            "bonus_time_minutes",
            "created_at",
        ]
        read_only_fields = fields
