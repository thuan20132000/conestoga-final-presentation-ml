from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django_filters import rest_framework as filters

from main.viewsets import BaseModelViewSet
from staff.models import Staff
from staff.permissions import IsBusinessManagerOrReceptionist
from .models import StaffTurn, TurnService as TurnServiceModel
from .serializers import (
    CompleteServiceSerializer,
    JoinedStaffWithHistorySerializer,
    MarkInServiceSerializer,
    NextTurnSerializer,
    StaffTurnReorderSerializer,
    StaffTurnSerializer,
    StaffTurnServiceAssignmentSerializer,
    TurnSerializer,
    TurnServiceSerializer,
    UpdateTurnSerializer,
    StaffTurnPrioritySerializer,
)
from .services import StaffTurnService, TurnServiceManager


class StaffTurnFilter(filters.FilterSet):
    business_id = filters.UUIDFilter(field_name='business_id', required=True)
    date = filters.DateFilter(field_name='date', required=False)

    class Meta:
        model = StaffTurn
        fields = ['business_id', 'date']


class StaffTurnViewSet(BaseModelViewSet):
    """ViewSet for staff turn queue management."""

    queryset = StaffTurn.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    filterset_class = StaffTurnFilter
    serializer_class = StaffTurnSerializer

    def _get_business_id(self, request):
        return request.query_params.get('business_id') or request.user.business_id

    def list(self, request, *args, **kwargs):
        """Get the turn queue for a business. Defaults to today."""
        try:
            business_id = self._get_business_id(request)
            date_str = request.query_params.get('date')
            date = date_str or timezone.now().date()
            queue = StaffTurnService.get_queue(business_id=business_id, date=date)
            serializer = StaffTurnSerializer(queue, many=True)
            return self.response_success(serializer.data)
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['get'], url_path='joined')
    def joined_staffs(self, request):
        """Get all joined staff with their turn history for the day."""
        try:
            business_id = self._get_business_id(request)
            date_str = request.query_params.get('date')
            date = date_str or timezone.now().date()
            results = StaffTurnService.get_joined_staffs(
                business_id=business_id, date=date
            )
            joined_staffs = JoinedStaffWithHistorySerializer(results, many=True).data
            return self.response_success(joined_staffs)
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['get'], url_path='next-turns')
    def next_turn(self, request):
        """Get the next staff who should serve based on service price.
        Full turn (price > threshold): first available (front of queue).
        Half turn (price <= threshold): last available (back of queue).
        No price: defaults to first available.
        """
        try:
            business_id = self._get_business_id(request)
            date_str = request.query_params.get('date')
            date = date_str or timezone.now().date()
            turn_service_id = request.query_params.get('turn_service_id')
            service_price = request.query_params.get('service_price')

            result = StaffTurnService.get_next_turns(
                business_id=business_id,
                turn_service_id=turn_service_id,
                service_price=service_price,
                date=date,
            )
            if not result:
                return self.response_success(None, message="No available staff in queue")

            next_turns = StaffTurnPrioritySerializer(result, many=True).data

            return self.response_success(next_turns)
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='send-to-back')
    def send_to_back(self, request):
        """Move a staff to the back of the queue after they finish serving."""
        try:
            staff_turn_id = request.data.get('staff_turn_id')
            date = request.data.get('date', timezone.now().date())
            business_id = self._get_business_id(request)
            staff_turn = StaffTurnService.send_to_back(business_id, staff_turn_id, date=date)
            return self.response_success(StaffTurnSerializer(staff_turn).data)
        except StaffTurn.DoesNotExist:
            return self.response_error("Staff turn not found")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='send-to-top')
    def send_to_top(self, request):
        """Move a staff to the top of the queue."""
        try:
            staff_turn_id = request.data.get('staff_turn_id')
            date = request.data.get('date', timezone.now().date())
            business_id = self._get_business_id(request)
            staff_turn = StaffTurnService.send_to_top(business_id, staff_turn_id, date=date)
            return self.response_success(StaffTurnSerializer(staff_turn).data)
        except StaffTurn.DoesNotExist:
            return self.response_error("Staff turn not found")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='mark-in-service')
    def mark_in_service(self, request):
        """Mark a staff as in service (currently serving).
        Creates a Turn record linked to the turn service.
        """
        try:
            serializer = MarkInServiceSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            business_id = self._get_business_id(request)
            turn_type = serializer.validated_data.get('turn_type', None)
            is_client_request = serializer.validated_data.get('is_client_request', False)
            date = serializer.validated_data.get('date', timezone.now().date())
            turn = StaffTurnService.mark_in_service(
                business_id=business_id,
                staff_turn_id=serializer.validated_data.get('staff_turn_id'),
                turn_service_id=serializer.validated_data.get('turn_service_id'),
                service_price=serializer.validated_data.get('service_price'),
                turn_type=turn_type,
                date=date,
                is_client_request=is_client_request,
            )
            return self.response_success(
                TurnSerializer(turn).data,
                message="Staff marked as in service",
            )
        except Staff.DoesNotExist:
            return self.response_error("Staff not found")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """Manually reorder the entire queue."""
        try:
            serializer = StaffTurnReorderSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            business_id = self._get_business_id(request)
            ordered_staff_turn_ids = serializer.validated_data.get('ordered_staff_turn_ids', [])
            date = serializer.validated_data.get('date', timezone.now().date())
            StaffTurnService.reorder_queue(
                business_id=business_id,
                ordered_staff_turn_ids=ordered_staff_turn_ids,
                date=date,
            )
            queue = StaffTurnService.get_queue(business_id, date)
            return self.response_success(StaffTurnSerializer(queue, many=True).data)
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='skip')
    def skip_turn(self, request):
        """Skip a staff member's turn (move them one position back)."""
        try:
            staff_id = request.data.get('staff_id')
            date = request.data.get('date', timezone.now().date())
            staff = Staff.objects.get(
                id=staff_id, business_id=self._get_business_id(request)
            )
            turn = StaffTurnService.skip_turn(staff, date=date)
            return self.response_success(StaffTurnSerializer(turn).data)
        except Staff.DoesNotExist:
            return self.response_error("Staff not found")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='join')
    def join_queue(self, request):
        """Manually add a staff to the turn queue."""
        try:
            staff_id = request.data.get('staff_id')
            date = request.data.get('date', timezone.now().date())
            staff = Staff.objects.get(
                id=staff_id, business_id=self._get_business_id(request)
            )
            turn = StaffTurnService.join_queue(staff, date=date)
            return self.response_success(StaffTurnSerializer(turn).data)
        except Staff.DoesNotExist:
            return self.response_error("Staff not found")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='leave')
    def leave_queue(self, request):
        """Manually remove a staff from the turn queue."""
        try:
            staff_turn_id = request.data.get('staff_turn_id')
            date = request.data.get('date', timezone.now().date())
            staff_turn = StaffTurn.objects.get(
                business_id=self._get_business_id(request),
                id=staff_turn_id,
                date=date,
                is_deleted=False,
            )
            in_service = StaffTurnService.check_if_staff_is_in_service(staff_turn, date=date)
            if in_service:
                return self.response_error(
                    data=None,
                    message="Staff is in service, please complete the service first"
                )

            StaffTurnService.leave_queue(staff_turn=staff_turn)
            return self.response_success(None, message="Staff removed from queue")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='update-turn')
    def update_turn(self, request):
        """Update an existing turn's details (turn service, price, turn type, client request)."""
        try:
            serializer = UpdateTurnSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            turn_id = data.pop('turn_id')
            turn = StaffTurnService.update_turn(turn_id=turn_id, **data)
            return self.response_success(TurnSerializer(turn).data)
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='delete-turn')
    def delete_turn(self, request):
        """Soft-delete a turn record."""
        try:
            turn_id = request.data.get('turn_id')
            staff_turn_id = request.data.get('staff_turn_id')
            
            if not turn_id or not staff_turn_id:
                return self.response_error("turn_id and staff_turn_id are required")
            StaffTurnService.delete_turn(turn_id=turn_id, staff_turn_id=staff_turn_id)
            return self.response_success(None, message="Turn deleted successfully")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['post'], url_path='complete-service')
    def complete_service(self, request):
        """Complete a service and update queue position.
        Uses the turn type stored when staff was marked busy.
        """
        try:
            serializer = CompleteServiceSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            business_id = self._get_business_id(request)
            date = serializer.validated_data.get('date', timezone.now().date())
            staff_turn_id = serializer.validated_data.get('staff_turn_id')
            turn = StaffTurnService.complete_service(
                business_id=business_id,
                staff_turn_id=staff_turn_id,
                date=date,
            )
            return self.response_success(StaffTurnSerializer(turn).data)
        except Staff.DoesNotExist:
            return self.response_error("Staff not found")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['get'], url_path='completed')
    def completed_turns(self, request):
        """Get all completed turns grouped by staff, with individual turn records."""
        try:
            business_id = self._get_business_id(request)
            date_str = request.query_params.get('date')
            date = date_str or timezone.now().date()
            results = StaffTurnService.get_completed_turns(
                business_id=business_id, date=date
            )
            data = [
                {
                    'staff_id': r['staff_id'],
                    'staff_name': r['staff_name'],
                    'staff_photo': r['staff_photo'],
                    'total_turns': r['total_turns'],
                    'full_turns': r['full_turns'],
                    'half_turns': r['half_turns'],
                    'turns': TurnSerializer(r['turns'], many=True).data,
                }
                for r in results
            ]
            return self.response_success(data)
        except Exception as e:
            return self.response_error(str(e))


# ---------------------------------------------------------------------------
# TurnService CRUD + staff assignment management
# ---------------------------------------------------------------------------

class TurnServiceFilter(filters.FilterSet):
    business_id = filters.UUIDFilter(field_name='business_id', required=True)

    class Meta:
        model = TurnServiceModel
        fields = ['business_id']


class TurnServiceViewSet(BaseModelViewSet):
    """CRUD for TurnService and staff assignment management."""

    queryset = TurnServiceModel.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated, IsBusinessManagerOrReceptionist]
    filterset_class = TurnServiceFilter
    serializer_class = TurnServiceSerializer

    def _get_business_id(self, request):
        return (
            request.query_params.get('business_id')
            or request.data.get('business_id')
            or request.user.business_id
        )

    def list(self, request, *args, **kwargs):
        try:
            business_id = self._get_business_id(request)
            qs = TurnServiceManager.get_turn_services(business_id)
            return self.response_success(TurnServiceSerializer(qs, many=True).data)
        except Exception as e:
            return self.response_error(str(e))

    def create(self, request, *args, **kwargs):
        try:
            from business.models import Business
            business_id = self._get_business_id(request)
            business = Business.objects.get(id=business_id)
            name = request.data.get('name')
            service_ids = request.data.get('service_ids', [])
            ts = TurnServiceManager.create_turn_service(
                business=business, name=name, service_ids=service_ids
            )
            return self.response_success(TurnServiceSerializer(ts).data)
        except Exception as e:
            return self.response_error(str(e))

    def update(self, request, *args, **kwargs):
        try:
            ts = TurnServiceManager.update_turn_service(
                turn_service_id=kwargs['pk'],
                name=request.data.get('name'),
                is_active=request.data.get('is_active'),
                service_ids=request.data.get('service_ids'),
            )
            return self.response_success(TurnServiceSerializer(ts).data)
        except Exception as e:
            return self.response_error(str(e))

    def destroy(self, request, *args, **kwargs):
        try:
            TurnServiceManager.delete_turn_service(kwargs['pk'])
            return self.response_success(None, message="Turn service deleted")
        except Exception as e:
            return self.response_error(str(e))

    # ------ staff assignment actions ------

    @action(detail=True, methods=['post'], url_path='assign-staff')
    def assign_staff(self, request, pk=None):
        """Assign staff members to this turn service."""
        try:
            staff = Staff.objects.get(id=request.data.get('staff_id'))
            assignment = TurnServiceManager.assign_staff(pk, staff)
            return self.response_success(
                StaffTurnServiceAssignmentSerializer(assignment).data,
                message="Staff assigned",
            )
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=True, methods=['post'], url_path='remove-staff')
    def remove_staff(self, request, pk=None):
        """Remove staff members from this turn service."""
        try:
            staff_id = request.data.get('staff_id', None)
            if not staff_id:
                return self.response_error("staff_id is required")
            TurnServiceManager.remove_staff(pk, staff_id)
            return self.response_success(None, message="Staff removed")
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=True, methods=['get'], url_path='staff')
    def staff_list(self, request, pk=None):
        """List staff assigned to this turn service."""
        try:
            assignments = TurnServiceManager.get_staff_for_turn_service(pk)
            return self.response_success(
                StaffTurnServiceAssignmentSerializer(assignments, many=True).data,
            )
        except Exception as e:
            return self.response_error(str(e))

    @action(detail=False, methods=['get'], url_path='by-staff')
    def by_staff(self, request):
        """List turn services assigned to a specific staff member."""
        try:
            staff_id = request.query_params.get('staff_id')
            if not staff_id:
                return self.response_error("staff_id is required")
            qs = TurnServiceManager.get_turn_services_for_staff(staff_id)
            return self.response_success(TurnServiceSerializer(qs, many=True).data)
        except Exception as e:
            return self.response_error(str(e))
