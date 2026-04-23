import uuid
import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime, parse_date
from datetime import datetime

from client.models import Client
from business.models import Business


class Command(BaseCommand):
    help = 'Migrate clients from business-clients.csv to Client model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=uuid.UUID,
            required=True,
            help='Business ID to associate clients with'
        )
        parser.add_argument(
            '--csv-file',
            type=str,
            default='business-clients.csv',
            help='Path to CSV file (default: business-clients.csv)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually creating clients (for testing)'
        )
      
    def handle(self, *args, **options):
        business_id = options['business_id']
        csv_file = options['csv_file']
        dry_run = options['dry_run']

        # Validate business exists
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Business with ID {business_id} not found.')
            )
            return

        # Check if CSV file exists
        if not os.path.exists(csv_file):
            self.stdout.write(
                self.style.ERROR(f'CSV file not found: {csv_file}')
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No clients will be created'))

        self.stdout.write(f'Starting migration from {csv_file}...')
        self.stdout.write(f'Target business: {business.name} (ID: {business_id})')

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header row
                for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is header
                    try:
                        # Parse and validate data
                        first_name = row[2].strip()
                        phone = row[3].strip()
                        email = row[4].strip()
                        date_of_birth = parse_date(row[5].strip())
                        
                        # create client
                        if not dry_run:
                            client = Client.objects.create(
                                first_name=first_name,
                                last_name='',
                                email=email,
                                phone=phone,
                                date_of_birth=date_of_birth,
                                primary_business=business,
                                is_active=True,
                                is_vip=False
                            )
                        else:
                            self.stdout.write(f'Would create client: {first_name} {email} {phone} {date_of_birth}')
                        created_count += 1

                        if (created_count + updated_count + skipped_count + error_count) % 100 == 0:
                            self.stdout.write(
                                f'Processed {created_count + updated_count + skipped_count + error_count} rows...'
                            )

                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'Error processing row {row_num}: {str(e)}'
                            )
                        )
                        continue

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error reading CSV file: {str(e)}')
            )
            return

        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('Migration Summary:'))
        self.stdout.write(self.style.SUCCESS('='*50))
        if dry_run:
            self.stdout.write(f'Would create: {created_count} clients')
        else:
            self.stdout.write(f'Created: {created_count} clients')
            self.stdout.write(f'Updated: {updated_count} clients')
        self.stdout.write(f'Skipped: {skipped_count} rows')
        self.stdout.write(f'Errors: {error_count} rows')
        self.stdout.write(self.style.SUCCESS('='*50))
