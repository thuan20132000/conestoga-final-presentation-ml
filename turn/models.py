from django.db import models
from main.models import SoftDeleteModel

DEFAULT_HALF_TURN_THRESHOLD = 25.00


class TurnType(models.TextChoices):
    FULL = 'FULL', 'Full Turn'
    HALF = 'HALF', 'Half Turn'


class TurnStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_SERVICE = 'in_service', 'In Service'
    COMPLETED = 'completed', 'Completed'
    
    
class StaffTurn(SoftDeleteModel):
    """Tracks staff turn order in the FIFO queue per business per day."""

    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='staff_turns',
    )
    staff = models.ForeignKey(
        'staff.Staff',
        on_delete=models.CASCADE,
        related_name='staff_turns',
    )
    position = models.PositiveIntegerField(
        help_text="Position in the turn queue (lower = sooner to serve)",
    )
    date = models.DateField(
        help_text="The date this turn applies to",
    )
    is_available = models.BooleanField(
        default=True,
        help_text="Whether the staff is currently available (not busy serving)",
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the staff joined the queue",
    )
    

    class Meta:
        unique_together = ['business', 'staff', 'date']
        ordering = ['position']
        indexes = [
            models.Index(fields=['business', 'date', 'position']),
        ]

    def __str__(self):
        return f"{self.staff.get_full_name()} - Position {self.position} ({self.date})"

class TurnService(SoftDeleteModel):
    """A named group of services that can be assigned during a turn."""

    business = models.ForeignKey(
        'business.Business',
        on_delete=models.CASCADE,
        related_name='turn_services',
    )
    name = models.CharField(max_length=200)
    services = models.ManyToManyField(
        'service.Service',
        related_name='turn_services',
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['business', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.business.name} - {self.name}"


class StaffTurnServiceAssignment(SoftDeleteModel):
    """Links staff to turn services they can handle."""

    staff = models.ForeignKey(
        'staff.Staff',
        on_delete=models.CASCADE,
        related_name='turn_service_assignments',
    )
    turn_service = models.ForeignKey(
        'TurnService',
        on_delete=models.CASCADE,
        related_name='staff_assignments',
    )

    class Meta:
        unique_together = ['staff', 'turn_service']

    def __str__(self):
        return f"{self.staff.get_full_name()} - {self.turn_service.name}"


class Turn(SoftDeleteModel):
    """Tracks each turn for a staff."""

    staff_turn = models.ForeignKey(
        'StaffTurn',
        on_delete=models.CASCADE,
        related_name='turn',
        null=True,
        blank=True,
    )

    turn_service = models.ForeignKey(
        'TurnService',
        on_delete=models.CASCADE,
        related_name='turns',
        null=True,
        blank=True,
    )
    service_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total price for this turn",
        null=True,
        blank=True,
        default=0,
    )

    in_service_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the turn was started",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the turn was completed",
    )

    status = models.CharField(
        max_length=10,
        choices=TurnStatus.choices,
        default=TurnStatus.PENDING.value,
    )

    turn_type = models.CharField(
        max_length=10,
        choices=TurnType.choices,
        null=True,
        blank=True,
        help_text="Turn type for the current service (set when marked busy, cleared on complete)",
    )

    is_client_request = models.BooleanField(
        default=False,
        help_text="Whether the staff was requested by the client",
    )

    class Meta:
        unique_together = ['staff_turn', 'turn_service', 'created_at']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['staff_turn', 'turn_service', 'created_at']),
        ]

    def __str__(self):
        return f"{self.staff_turn.staff.get_full_name()}"


