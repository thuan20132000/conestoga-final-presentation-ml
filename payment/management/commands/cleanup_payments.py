from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, models
from payment.models import Payment, PaymentStatus


class Command(BaseCommand):
    help = 'Cleanup old and failed payments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to keep old failed payments (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options.get('days')
        dry_run = options.get('dry_run')
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            self.style.WARNING(f'Cleaning up payments older than {days} days (before {cutoff_date.date()})')
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('')
        
        # Get failed status
        try:
            failed_status = PaymentStatus.objects.get(name='failed')
            pending_status = PaymentStatus.objects.get(name='pending')
        except PaymentStatus.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Required payment statuses not found. Please run create_payment_statuses first.')
            )
            return
        
        # Find old failed payments
        old_failed_payments = Payment.objects.filter(
            Q(status=failed_status) | Q(status=pending_status),
            created_at__lt=cutoff_date
        )
        
        count = old_failed_payments.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No old failed or pending payments found to cleanup.')
            )
            return
        
        self.stdout.write(f'Found {count} old failed/pending payments to cleanup:')
        
        # Show breakdown by status
        status_breakdown = old_failed_payments.values('status__name').distinct().count()
        for status_name in old_failed_payments.values_list('status__name', flat=True).distinct():
            status_count = old_failed_payments.filter(status__name=status_name).count()
            self.stdout.write(f'  {status_name}: {status_count} payments')
        
        self.stdout.write('')
        
        # Show breakdown by business
        business_breakdown = old_failed_payments.values('business__name').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        self.stdout.write('Breakdown by business:')
        for business_stat in business_breakdown:
            business_name = business_stat['business__name']
            business_count = business_stat['count']
            self.stdout.write(f'  {business_name}: {business_count} payments')
        
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {count} payments')
            )
            self.stdout.write('Run without --dry-run to actually delete these payments.')
        else:
            # Confirm deletion
            confirm = input(f'Are you sure you want to delete {count} payments? (yes/no): ')
            
            if confirm.lower() in ['yes', 'y']:
                deleted_count = old_failed_payments.count()
                old_failed_payments.delete()
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully deleted {deleted_count} old payments.')
                )
            else:
                self.stdout.write(self.style.WARNING('Deletion cancelled.'))
        
        self.stdout.write('')
        
        # Additional cleanup suggestions
        self.stdout.write(self.style.WARNING('Additional cleanup suggestions:'))
        
        # Find payments with missing external transaction IDs
        missing_txn_payments = Payment.objects.filter(
            external_transaction_id__isnull=True,
            status__name__in=['completed', 'processing']
        ).count()
        
        if missing_txn_payments > 0:
            self.stdout.write(f'  - {missing_txn_payments} completed/processing payments missing external transaction IDs')
        
        # Find payments with empty gateway responses
        empty_response_payments = Payment.objects.filter(
            gateway_response__isnull=True,
            status__name__in=['completed', 'failed']
        ).count()
        
        if empty_response_payments > 0:
            self.stdout.write(f'  - {empty_response_payments} payments missing gateway responses')
        
        # Find orphaned payment splits
        from payment.models import PaymentSplit
        orphaned_splits = PaymentSplit.objects.filter(payment__isnull=True).count()
        
        if orphaned_splits > 0:
            self.stdout.write(f'  - {orphaned_splits} orphaned payment splits')
        
        if missing_txn_payments == 0 and empty_response_payments == 0 and orphaned_splits == 0:
            self.stdout.write('  - No additional cleanup needed!')
