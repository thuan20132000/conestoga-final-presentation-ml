from django.core.management.base import BaseCommand
from payment.models import PaymentStatus


class Command(BaseCommand):
    help = 'Create default payment statuses'

    def handle(self, *args, **options):
        statuses = [
            {
                'name': 'pending',
                'description': 'Payment is pending processing',
                'color': '#ffc107',
                'sort_order': 1
            },
            {
                'name': 'processing',
                'description': 'Payment is being processed',
                'color': '#17a2b8',
                'sort_order': 2
            },
            {
                'name': 'completed',
                'description': 'Payment has been completed successfully',
                'color': '#28a745',
                'sort_order': 3
            },
            {
                'name': 'failed',
                'description': 'Payment processing failed',
                'color': '#dc3545',
                'sort_order': 4
            },
            {
                'name': 'cancelled',
                'description': 'Payment was cancelled',
                'color': '#6c757d',
                'sort_order': 5
            },
            {
                'name': 'refunded',
                'description': 'Payment has been fully refunded',
                'color': '#fd7e14',
                'sort_order': 6
            },
            {
                'name': 'partially_refunded',
                'description': 'Payment has been partially refunded',
                'color': '#e83e8c',
                'sort_order': 7
            },
            {
                'name': 'chargeback',
                'description': 'Payment has been charged back',
                'color': '#6f42c1',
                'sort_order': 8
            },
        ]

        created_count = 0
        for status_data in statuses:
            status, created = PaymentStatus.objects.get_or_create(
                name=status_data['name'],
                defaults=status_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created payment status: {status.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Payment status already exists: {status.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} payment statuses')
        )
