from django.core.management.base import BaseCommand
from appointment.models import AppointmentStatus


class Command(BaseCommand):
    help = 'Create default appointment statuses'

    def handle(self, *args, **options):
        statuses = [
            {
                'name': 'scheduled',
                'description': 'Appointment has been scheduled but not yet confirmed',
                'color': '#007bff',
                'sort_order': 1
            },
            {
                'name': 'confirmed',
                'description': 'Appointment has been confirmed by client',
                'color': '#28a745',
                'sort_order': 2
            },
            {
                'name': 'in_progress',
                'description': 'Appointment is currently in progress',
                'color': '#ffc107',
                'sort_order': 3
            },
            {
                'name': 'completed',
                'description': 'Appointment has been completed successfully',
                'color': '#17a2b8',
                'sort_order': 4
            },
            {
                'name': 'cancelled',
                'description': 'Appointment has been cancelled',
                'color': '#dc3545',
                'sort_order': 5
            },
            {
                'name': 'no_show',
                'description': 'Client did not show up for the appointment',
                'color': '#6c757d',
                'sort_order': 6
            },
            {
                'name': 'rescheduled',
                'description': 'Appointment has been rescheduled',
                'color': '#fd7e14',
                'sort_order': 7
            }
        ]

        for status_data in statuses:
            status, created = AppointmentStatus.objects.get_or_create(
                name=status_data['name'],
                defaults=status_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created appointment status: {status.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Appointment status already exists: {status.name}')
                )

        self.stdout.write(
            self.style.SUCCESS('Successfully created default appointment statuses')
        )
