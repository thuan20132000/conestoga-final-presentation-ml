from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from client.models import Client


class Command(BaseCommand):
    help = 'Clean up client data (remove duplicates, inactive clients, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without actually doing it'
        )
        parser.add_argument(
            '--remove-duplicates',
            action='store_true',
            help='Remove duplicate clients (same email or phone)'
        )
        parser.add_argument(
            '--remove-inactive',
            action='store_true',
            help='Remove inactive clients older than specified days'
        )
        parser.add_argument(
            '--inactive-days',
            type=int,
            default=365,
            help='Days after which inactive clients should be removed (default: 365)'
        )
        parser.add_argument(
            '--clean-history',
            action='store_true',
            help='Clean up old history entries'
        )
        parser.add_argument(
            '--history-days',
            type=int,
            default=730,
            help='Days after which history entries should be removed (default: 730)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        remove_duplicates = options['remove_duplicates']
        remove_inactive = options['remove_inactive']
        inactive_days = options['inactive_days']
        
        self.stdout.write(self.style.SUCCESS('=== CLIENT CLEANUP ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        total_removed = 0
        
        # Remove duplicates
        if remove_duplicates:
            removed = self._remove_duplicates(dry_run)
            total_removed += removed
            self.stdout.write(f'Removed {removed} duplicate clients\n')
        
        # Remove inactive clients
        if remove_inactive:
            removed = self._remove_inactive_clients(dry_run, inactive_days)
            total_removed += removed
            self.stdout.write(f'Removed {removed} inactive clients\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Would remove {total_removed} items total'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully removed {total_removed} items'))

    def _remove_duplicates(self, dry_run):
        """Remove duplicate clients based on email or phone"""
        removed_count = 0
        
        # Find duplicates by email
        email_duplicates = (
            Client.objects
            .exclude(email__isnull=True)
            .exclude(email='')
            .values('email')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )
        
        for duplicate in email_duplicates:
            clients_with_email = Client.objects.filter(email=duplicate['email']).order_by('created_at')
            # Keep the first one, remove the rest
            clients_to_remove = clients_with_email[1:]
            
            for client in clients_to_remove:
                if not dry_run:
                    client.delete()
                removed_count += 1
                self.stdout.write(f'  Removing duplicate client: {client.get_full_name()} (email: {client.email})')
        
        # Find duplicates by phone
        phone_duplicates = (
            Client.objects
            .exclude(phone__isnull=True)
            .exclude(phone='')
            .values('phone')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )
        
        for duplicate in phone_duplicates:
            clients_with_phone = Client.objects.filter(phone=duplicate['phone']).order_by('created_at')
            # Keep the first one, remove the rest
            clients_to_remove = clients_with_phone[1:]
            
            for client in clients_to_remove:
                if not dry_run:
                    client.delete()
                removed_count += 1
                self.stdout.write(f'  Removing duplicate client: {client.get_full_name()} (phone: {client.phone})')
        
        return removed_count

    def _remove_inactive_clients(self, dry_run, inactive_days):
        """Remove inactive clients older than specified days"""
        cutoff_date = timezone.now() - timedelta(days=inactive_days)
        
        inactive_clients = Client.objects.filter(
            is_active=False,
            updated_at__lt=cutoff_date
        )
        
        removed_count = 0
        for client in inactive_clients:
            if not dry_run:
                client.delete()
            removed_count += 1
            self.stdout.write(f'  Removing inactive client: {client.get_full_name()} (last updated: {client.updated_at})')
        
        return removed_count

