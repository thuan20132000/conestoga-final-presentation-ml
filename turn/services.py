from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from .models import (
    StaffTurn, Turn, TurnService, StaffTurnServiceAssignment,
    TurnStatus, TurnType, DEFAULT_HALF_TURN_THRESHOLD,
)


class StaffTurnService:

    @staticmethod
    def _get_threshold(business_id):
        """Get the half turn threshold for a business from its settings."""
        from business.models import BusinessSettings
        try:
            settings = BusinessSettings.objects.get(business_id=business_id)
            return settings.half_turn_threshold
        except BusinessSettings.DoesNotExist:
            return Decimal(str(DEFAULT_HALF_TURN_THRESHOLD))

    @staticmethod
    def _get_next_position(business_id, date):
        max_pos = StaffTurn.objects.filter(
            business_id=business_id,
            date=date,
            is_deleted=False,
        ).aggregate(max_pos=models.Max('position'))['max_pos']
        return (max_pos or 0) + 1

    @staticmethod
    @transaction.atomic
    def join_queue(staff, date=None):
        """Add staff to the back of the turn queue.
        If a soft-deleted entry exists for the same day, restore it.
        """
        date = date or timezone.now().date()
        try:
            turn = StaffTurn.objects.get(
                business=staff.business,
                staff=staff,
                date=date,
            )
            # Restore if soft-deleted, or just mark available
            turn.is_deleted = False
            turn.deleted_at = None
            turn.is_available = True
            turn.position = StaffTurnService._get_next_position(
                staff.business_id, date
            )
            turn.save(update_fields=[
                'is_deleted', 'deleted_at', 'is_available',
                'position', 'updated_at',
            ])
            return turn
        except StaffTurn.DoesNotExist:
            return StaffTurn.objects.create(
                business=staff.business,
                staff=staff,
                date=date,
                position=StaffTurnService._get_next_position(
                    staff.business_id, date
                ),
                is_available=True,
            )


    @staticmethod
    @transaction.atomic
    def leave_queue(staff_turn):
        """Remove staff from the turn queue (soft-delete)."""
        staff_turn.is_deleted = True
        staff_turn.deleted_at = timezone.now()
        staff_turn.save(update_fields=['is_deleted', 'deleted_at', 'updated_at', 'date'])
        return staff_turn
    
    @staticmethod
    def get_queue(business_id, date=None):
        """Get the full ordered turn queue for a business on a given date."""
        date = date or timezone.now().date()
        return (
            StaffTurn.objects.filter(
                business_id=business_id,
                date=date,
                is_deleted=False,
            )
            .select_related('staff')
            .order_by('position')
        )

    @staticmethod
    def get_joined_staffs(business_id, date=None):
        """Get the turn queue with each staff's turn records for the day."""
        date = date or timezone.now().date()
        return (
            StaffTurn.objects.filter(
                business_id=business_id,
                date=date,
                is_deleted=False,
            )
            .select_related('staff')
            .prefetch_related('turn__turn_service__services')
            .order_by('joined_at')
        )

    @staticmethod
    def _get_eligible_staff_ids(turn_service_id):
        """Get staff IDs who are assigned to a given turn service."""
        return list(
            StaffTurnServiceAssignment.objects.filter(
                turn_service_id=turn_service_id,
                is_deleted=False,
            ).values_list('staff_id', flat=True)
        )

    @staticmethod
    def get_next_available(business_id, date=None, turn_service_id=None):
        """Get the next available staff member in the queue.
        If turn_service_id is provided, only considers staff assigned to that turn service.
        """
        date = date or timezone.now().date()
        qs = StaffTurn.objects.filter(
            business_id=business_id,
            date=date,
            is_deleted=False,
            is_available=True,
        )
        if turn_service_id:
            eligible_ids = StaffTurnService._get_eligible_staff_ids(turn_service_id)
            qs = qs.filter(staff_id__in=eligible_ids)
        return qs.select_related('staff').order_by('position')

    @staticmethod
    @transaction.atomic
    def send_to_back(business_id, staff_turn_id, date=None):
        """Move a staff member to the back of the queue after finishing service."""
        date = date or timezone.now().date()
        try:
            staff_turn = StaffTurn.objects.select_for_update().get(
                business_id=business_id,
                id=staff_turn_id,
                date=date,
                is_deleted=False,
            )
        except StaffTurn.DoesNotExist:
            raise ValueError("Staff turn not found")

        staff_turn.position = StaffTurnService._get_next_position(
            business_id, date
        )
        staff_turn.is_available = True
        staff_turn.save(update_fields=['position', 'is_available', 'updated_at'])
        return staff_turn

    @staticmethod
    @transaction.atomic
    def send_to_top(business_id, staff_turn_id, date=None):
        """Move a staff member to the top of the queue."""
        date = date or timezone.now().date()
        try:
            staff_turn = StaffTurn.objects.select_for_update().get(
                business_id=business_id,
                id=staff_turn_id,
                date=date,
                is_deleted=False,
            )
        except StaffTurn.DoesNotExist:
            raise ValueError("Staff turn not found")

        staff_turn.position = 1
        staff_turn.save(update_fields=['position', 'updated_at', 'is_available'])
        return staff_turn

    @staticmethod
    @transaction.atomic
    def mark_in_service(
        business_id,
        staff_turn_id,
        turn_service_id=None,
        service_price=None,
        turn_type=None,
        date=None,
        is_client_request=False
    ):
        """Mark a staff member as in service and create a Turn record.

        FULL turn: staff becomes unavailable (busy serving).
        HALF turn: staff stays available and keeps position.
        """
        date = date or timezone.now().date()
        try:
            staff_turn = StaffTurn.objects.select_for_update().get(
                business_id=business_id,
                id=staff_turn_id,
                date=date,
                is_deleted=False,
            )
        except StaffTurn.DoesNotExist:
            raise ValueError("Staff is not in the turn queue")

        turn_type = turn_type or TurnType.FULL.value

        if turn_type != TurnType.HALF.value:
            staff_turn.is_available = False
            staff_turn.save(update_fields=['is_available', 'updated_at'])

        turn = Turn.objects.create(
            staff_turn=staff_turn,
            turn_service_id=turn_service_id,
            service_price=service_price or 0,
            status=TurnStatus.IN_SERVICE,
            in_service_at=timezone.now(),
            turn_type=turn_type,
            is_client_request=is_client_request,
        )
        return turn

    @staticmethod
    @transaction.atomic
    def mark_available(staff, date=None):
        """Mark a staff member as available."""
        date = date or timezone.now().date()
        StaffTurn.objects.filter(
            business=staff.business,
            staff=staff,
            date=date,
            is_deleted=False,
        ).update(is_available=True)

    @staticmethod
    @transaction.atomic
    def reorder_queue(business_id, ordered_staff_turn_ids, date=None):
        """Manually reorder the queue. ordered_staff_turn_ids is a list of staff turn IDs in desired order."""
        date = date or timezone.now().date()
        staff_turns = StaffTurn.objects.filter(
            business_id=business_id,
            date=date,
            is_deleted=False,
        ).select_for_update()

        for idx, staff_turn_id in enumerate(ordered_staff_turn_ids, start=1):
            staff_turn = staff_turns.get(id=staff_turn_id)
            if staff_turn:
                staff_turn.position = idx
                staff_turn.save()
                
        return staff_turns

    @staticmethod
    @transaction.atomic
    def skip_turn(staff, date=None):
        """Skip a staff member's turn — swap them with the next person in line."""
        date = date or timezone.now().date()
        try:
            turn = StaffTurn.objects.select_for_update().get(
                business=staff.business,
                staff=staff,
                date=date,
                is_deleted=False,
            )
        except StaffTurn.DoesNotExist:
            raise ValueError("Staff is not in the turn queue")

        next_turn = (
            StaffTurn.objects.select_for_update()
            .filter(
                business=staff.business,
                date=date,
                is_deleted=False,
                position__gt=turn.position,
            )
            .order_by('position')
            .first()
        )

        if next_turn:
            turn.position, next_turn.position = next_turn.position, turn.position
            turn.save(update_fields=['position', 'updated_at'])
            next_turn.save(update_fields=['position', 'updated_at'])

        return turn

    @staticmethod
    def get_turn_type(service_price, business_id=None):
        """Determine turn type based on service price and business threshold.
        Price > threshold → FULL turn, otherwise → HALF turn.
        """
        if business_id:
            threshold = StaffTurnService._get_threshold(business_id)
        else:
            threshold = Decimal(str(DEFAULT_HALF_TURN_THRESHOLD))
        if Decimal(str(service_price)) > threshold:
            return TurnType.FULL
        return TurnType.HALF

    @staticmethod
    def get_next_turns(business_id, turn_service_id=None, service_price=None, date=None):
        """Get the next staff member who should serve, based on service price.

        Full turn (price > threshold): first available staff (front of queue).
        Half turn (price <= threshold): last available staff (back of queue).
        No price provided: returns first available (front of queue).

        Returns a queryset of StaffTurn ordered by position.
        """
        date = date or timezone.now().date()

        nt = StaffTurn.objects.filter(
            business_id=business_id,
            date=date,
            is_deleted=False,
            is_available=True,
        )
        if turn_service_id:
            eligible_ids = StaffTurnService._get_eligible_staff_ids(turn_service_id)
            nt = nt.filter(staff_id__in=eligible_ids)

        return nt.select_related('staff').order_by('position').all()

    @staticmethod
    def get_last_available(business_id, date=None, turn_service_id=None):
        """Get the last available staff member in the queue (for half turns).
        If turn_service_id is provided, only considers staff assigned to that turn service.
        """
        date = date or timezone.now().date()
        qs = StaffTurn.objects.filter(
            business_id=business_id,
            date=date,
            is_deleted=False,
            is_available=True,
        )
        if turn_service_id:
            eligible_ids = StaffTurnService._get_eligible_staff_ids(turn_service_id)
            qs = qs.filter(staff_id__in=eligible_ids)
        return qs.select_related('staff').order_by('-position').first()

    @staticmethod
    @transaction.atomic
    def complete_service(business_id, staff_turn_id, date=None):
        """Complete a service and update queue position based on turn type.

        Full turn: staff goes to the back of the queue and becomes available.
        Half turn: staff stays in current position (was never marked unavailable).
        """
        date = date or timezone.now().date()
        try:
            staff_turn = StaffTurn.objects.select_for_update().get(
                business_id=business_id,
                id=staff_turn_id,
                date=date,
                is_deleted=False,
            )
        except StaffTurn.DoesNotExist:
            raise ValueError("Staff is not in the turn queue")

        # Mark the latest in-service Turn as completed
        latest_turn = (
            Turn.objects.filter(
                staff_turn=staff_turn,
                status=TurnStatus.IN_SERVICE,
                is_deleted=False,
            )
            .order_by('-created_at')
            .first()
        )

        turn_type = latest_turn.turn_type if latest_turn else TurnType.FULL.value

        if latest_turn:
            latest_turn.status = TurnStatus.COMPLETED
            latest_turn.completed_at = timezone.now()
            latest_turn.save(update_fields=['status', 'completed_at', 'updated_at'])

        # FULL turn: send to back and mark available
        # HALF turn: position unchanged, staff was already available
        if turn_type == TurnType.FULL.value:
            staff_turn.position = StaffTurnService._get_next_position(
                business_id, date
            )
            staff_turn.is_available = True
            staff_turn.save(update_fields=['position', 'is_available', 'updated_at'])

        return staff_turn

    @staticmethod
    def get_completed_turns(business_id, date=None):
        """Get all completed turns for a business, grouped by staff with individual turn records."""
        date = date or timezone.now().date()
        turns = (
            Turn.objects.filter(
                staff_turn__business_id=business_id,
                staff_turn__date=date,
                status=TurnStatus.COMPLETED,
                is_deleted=False,
            )
            .select_related('staff_turn__staff', 'turn_service')
            .prefetch_related('turn_service__services')
            .order_by('completed_at')
        )

        staff_map = {}
        for t in turns:
            sid = str(t.staff_turn.staff_id)
            if sid not in staff_map:
                staff = t.staff_turn.staff
                staff_map[sid] = {
                    'staff_id': t.staff_turn.staff_id,
                    'staff_name': staff.get_full_name(),
                    'staff_photo': staff.photo.url if staff.photo else None,
                    'total_turns': 0,
                    'full_turns': 0,
                    'half_turns': 0,
                    'turns': [],
                }
            entry = staff_map[sid]
            entry['total_turns'] += 1
            turn_type = StaffTurnService.get_turn_type(
                t.service_price, business_id
            )
            if turn_type == TurnType.FULL:
                entry['full_turns'] += 1
            else:
                entry['half_turns'] += 1
            entry['turns'].append(t)

        return list(staff_map.values())

    @staticmethod
    @transaction.atomic
    def update_turn(turn_id, **kwargs):
        """Update an existing Turn record's editable fields."""
        try:
            turn = Turn.objects.select_for_update().get(
                id=turn_id,
                is_deleted=False,
            )
        except Turn.DoesNotExist:
            raise ValueError("Turn not found")

        update_fields = []
        for field in ('turn_service_id', 'service_price', 'turn_type', 'is_client_request', 'completed_at', 'status'):
            if field in kwargs and kwargs[field] is not None:
                setattr(turn, field, kwargs[field])
                update_fields.append(field)

        if update_fields:
            update_fields.append('updated_at')
            turn.save(update_fields=update_fields)

        return turn

    @staticmethod
    @transaction.atomic
    def delete_turn(turn_id, staff_turn_id):
        """Soft-delete a Turn record."""
        try:
            turn = Turn.objects.get(id=turn_id, is_deleted=False)
            staff_turn = StaffTurn.objects.select_for_update().get(id=staff_turn_id, is_deleted=False)
            has_other_in_service = Turn.objects.filter(
                staff_turn_id=staff_turn_id,
                is_deleted=False,
                status=TurnStatus.IN_SERVICE,
                turn_type=TurnType.FULL.value,
            ).exclude(id=turn_id).exists()

            staff_turn.is_available = not has_other_in_service
            staff_turn.save(update_fields=['is_available', 'updated_at'])
            turn.is_deleted = True
            turn.deleted_at = timezone.now()
            turn.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
            return turn
        except (Turn.DoesNotExist, StaffTurn.DoesNotExist):
            raise ValueError("Turn or staff turn not found")

    @staticmethod
    def check_if_staff_is_in_service(staff_turn, date=None):
        """Check if a staff turn is in service."""
        date = date or timezone.now().date()
        return staff_turn.turn.filter(
            staff_turn=staff_turn,
            in_service_at__date=date,
            status=TurnStatus.IN_SERVICE,
            is_deleted=False,
        ).exists()


class TurnServiceManager:
    """Manages TurnService CRUD and staff assignment operations."""

    @staticmethod
    @transaction.atomic
    def create_turn_service(business, name, service_ids=None):
        ts = TurnService.objects.create(business=business, name=name)
        if service_ids:
            ts.services.set(service_ids)
        return ts

    @staticmethod
    @transaction.atomic
    def update_turn_service(turn_service_id, **kwargs):
        try:
            ts = TurnService.objects.get(id=turn_service_id, is_deleted=False)
        except TurnService.DoesNotExist:
            raise ValueError("Turn service not found")

        service_ids = kwargs.pop('service_ids', None)
        for field in ('name', 'is_active'):
            if field in kwargs and kwargs[field] is not None:
                setattr(ts, field, kwargs[field])
        ts.save()

        if service_ids is not None:
            ts.services.set(service_ids)

        return ts

    @staticmethod
    @transaction.atomic
    def delete_turn_service(turn_service_id):
        try:
            ts = TurnService.objects.get(id=turn_service_id, is_deleted=False)
        except TurnService.DoesNotExist:
            raise ValueError("Turn service not found")
        ts.is_deleted = True
        ts.deleted_at = timezone.now()
        ts.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
        return ts

    @staticmethod
    def get_turn_services(business_id):
        return (
            TurnService.objects.filter(business_id=business_id, is_deleted=False)
            .prefetch_related('services', 'staff_assignments__staff')
        )

    @staticmethod
    @transaction.atomic
    def assign_staff(turn_service_id, staff):
        """Bulk-assign staff to a turn service (idempotent)."""
        ts = TurnService.objects.get(id=turn_service_id, is_deleted=False)
        return StaffTurnServiceAssignment.objects.create(
            turn_service=ts,
            staff=staff,
        )

    @staticmethod
    @transaction.atomic
    def remove_staff(turn_service_id, staff_id):
        """Soft-delete staff assignments from a turn service."""
        return StaffTurnServiceAssignment.objects.filter(
            turn_service_id=turn_service_id,
            staff_id=staff_id,
            is_deleted=False,
        ).delete()

    @staticmethod
    def get_staff_for_turn_service(turn_service_id):
        """List staff assigned to a turn service."""
        return (
            StaffTurnServiceAssignment.objects.filter(
                turn_service_id=turn_service_id,
                is_deleted=False,
            )
            .select_related('staff')
        )

    @staticmethod
    def get_turn_services_for_staff(staff_id):
        """List turn services assigned to a staff member."""
        ts_ids = StaffTurnServiceAssignment.objects.filter(
            staff_id=staff_id,
            is_deleted=False,
        ).values_list('turn_service_id', flat=True)
        return TurnService.objects.filter(
            id__in=ts_ids,
            is_deleted=False,
        ).prefetch_related('services')