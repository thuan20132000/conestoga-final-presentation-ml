from rest_framework import serializers
from service.models import Service
from .models import (
    StaffTurn, Turn, TurnService, StaffTurnServiceAssignment,
    TurnStatus, TurnType,
)


class ServiceMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['id', 'name', 'price', 'duration_minutes']


class TurnServiceSerializer(serializers.ModelSerializer):
    services = ServiceMiniSerializer(many=True, read_only=True)
    service_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = TurnService
        fields = [
            'id',
            'business',
            'name',
            'services',
            'service_ids',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StaffTurnServiceAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.get_full_name', read_only=True)
    staff_id = serializers.IntegerField(source='staff.id', read_only=True)
    staff_photo = serializers.ImageField(source='staff.photo', read_only=True)
    turn_service_name = serializers.CharField(source='turn_service.name', read_only=True)

    class Meta:
        model = StaffTurnServiceAssignment
        fields = [
            'id',
            'staff_id',
            'staff_name',
            'staff_photo',
            'turn_service',
            'turn_service_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class StaffTurnSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.get_full_name', read_only=True)
    staff_id = serializers.IntegerField(source='staff.id', read_only=True)
    staff_photo = serializers.ImageField(source='staff.photo', read_only=True)    

    class Meta:
        model = StaffTurn
        fields = [
            'id',
            'business',
            'staff_id',
            'staff_name',
            'staff_photo',
            'position',
            'date',
            'is_available',
            'joined_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'joined_at', 'created_at', 'updated_at']


class StaffTurnReorderSerializer(serializers.Serializer):
    ordered_staff_turn_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of staff turn IDs in desired turn order. If not provided, the queue will be reordered based on the staff's position.",
        required=False,
        default=[],
    )
    date = serializers.DateField(required=False)


class AssignByServicePriceSerializer(serializers.Serializer):
    turn_service_id = serializers.IntegerField(
        required=False,
        help_text="Turn service ID — only staff assigned to this turn service will be considered",
    )
    service_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Service price to determine turn type (>threshold = full, <=threshold = half)",
    )
    date = serializers.DateField(required=False)


class MarkInServiceSerializer(serializers.Serializer):
    staff_turn_id = serializers.IntegerField()
    date = serializers.DateField(required=False)
    turn_service_id = serializers.IntegerField(
        help_text="Turn service ID for the turn",
        required=False,
    )
    turn_type = serializers.CharField(
        help_text="Turn type (FULL or HALF)",
        required=False,
        default=TurnType.FULL.value,
    )
    is_client_request = serializers.BooleanField(
        help_text="Whether the staff was requested by the client",
        required=False,
        default=False,
    )


class CompleteServiceSerializer(serializers.Serializer):
    staff_turn_id = serializers.IntegerField()
    date = serializers.DateField(required=False)


class TurnSerializer(serializers.ModelSerializer):
    turn_service_name = serializers.CharField(
        source='turn_service.name', read_only=True, default=None,
    )
    services = serializers.SerializerMethodField()

    class Meta:
        model = Turn
        fields = [
            'id',
            'turn_service',
            'turn_service_name',
            'services',
            'service_price',
            'status',
            'in_service_at',
            'turn_type',
            'is_client_request',
            'completed_at',
            'created_at',
        ]

    def get_services(self, obj):
        if obj.turn_service:
            return ServiceMiniSerializer(obj.turn_service.services.all(), many=True).data
        return []


class UpdateTurnSerializer(serializers.Serializer):
    turn_id = serializers.IntegerField()
    turn_service_id = serializers.IntegerField(required=False)
    service_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False,
    )
    turn_type = serializers.ChoiceField(
        choices=TurnType.choices, required=False,
    )
    is_client_request = serializers.BooleanField(required=False)
    completed_at = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(
        choices=TurnStatus.choices, required=False,
    )


class NextTurnSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.get_full_name', read_only=True)
    staff_photo = serializers.ImageField(source='staff.photo', read_only=True)

    class Meta:
        model = StaffTurn
        fields = [
            'id',
            'staff_id',
            'staff_name',
            'staff_photo',
            'position',
            'date',
            'is_available',
            'joined_at',
        ]


class JoinedStaffWithHistorySerializer(serializers.ModelSerializer):
    staff_id = serializers.IntegerField(source='staff.id', read_only=True)
    staff_name = serializers.CharField(source='staff.first_name', read_only=True)
    staff_photo = serializers.ImageField(source='staff.photo', read_only=True)
    turns = serializers.SerializerMethodField()

    class Meta:
        model = StaffTurn
        fields = [
            'id',
            'staff_id',
            'staff_name',
            'staff_photo',
            'position',
            'date',
            'is_available',
            'joined_at',
            'turns',
        ]

    def get_turns(self, obj):
        turns = obj.turn.filter(is_deleted=False).order_by('created_at')
        return TurnSerializer(turns, many=True).data

class StaffTurnPrioritySerializer(NextTurnSerializer):

    last_turn = serializers.SerializerMethodField()
    class Meta:
        model = StaffTurn
        fields = NextTurnSerializer.Meta.fields + ['last_turn']

    def get_last_turn(self, obj):
        lt = Turn.objects.filter(staff_turn=obj, is_deleted=False).order_by('-created_at').first()
        if lt:
            return TurnSerializer(lt).data
        return None