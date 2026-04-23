from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from business.models import Business
from service.models import Service
from staff.models import Staff, StaffService, StaffWorkingHours


class Command(BaseCommand):
    help = 'Create sample staff, roles, and working hours for existing businesses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id', type=int, help='Target a single business id'
        )
        parser.add_argument(
            '--per-business', type=int, default=3,
            help='Number of staff to create per business (default: 3)'
        )
        parser.add_argument(
            '--assign-services', action='store_true',
            help='Assign available services to staff (random primary)'
        )
        parser.add_argument(
            '--clear-existing', action='store_true',
            help='Remove existing Staff/StaffRole/StaffService/StaffWorkingHours for targeted businesses before creating'
        )

    def handle(self, *args, **options):
        business_id = options.get('business_id')
        per_business = options.get('per_business')
        assign_services = options.get('assign_services')
        clear_existing = options.get('clear_existing')
        
        if business_id:
            businesses = Business.objects.filter(id=business_id)
        else:
            businesses = Business.objects.all()

        if not businesses.exists():
            self.stdout.write(self.style.WARNING('No businesses found'))
            return

        for business in businesses:
            with transaction.atomic():
                if clear_existing:
                    self._clear_for_business(business)
                created = self._create_staff_for_business(
                    business, per_business)
                if assign_services:
                    self._assign_services_for_business(business)
                self.stdout.write(self.style.SUCCESS(
                    f"Business '{business.name}': created {created} staff"
                ))

    def _clear_for_business(self, business):
        StaffService.objects.filter(staff__business=business).delete()
        StaffWorkingHours.objects.filter(staff__business=business).delete()
        Staff.objects.filter(business=business).delete()


    def _create_staff_for_business(self, business, per_business):
        sample_people = [
            ('alex', 'Alex', 'Nguyen'),
            ('bella', 'Bella', 'Tran'),
            ('chris', 'Chris', 'Pham'),
            ('diana', 'Diana', 'Le'),
            ('eric', 'Eric', 'Vu'),
            ('fiona', 'Fiona', 'Do'),
            ('george', 'George', 'Hoang'),
        ]

        created_count = 0
        for idx, (username, first, last) in enumerate(sample_people[:per_business]):
            email = f"{username}@{business.name.replace(' ', '').lower()}.com"
            staff, created = Staff.objects.get_or_create(
                business=business,
                email=email,
                defaults={
                    'username': f"{username}-{business.id}",
                    'first_name': first,
                    'last_name': last,
                    'phone': business.phone_number or '+1-555-0000',
                    'is_active': True,
                    'hire_date': timezone.now().date(),
                }
            )
            if created:
                created_count += 1
                self._create_default_working_hours(staff)
        return created_count

    def _create_default_working_hours(self, staff):
        # Mon-Fri 09:00-17:00, Sat 10:00-16:00, Sun off
        from datetime import time

        defaults = {
            0: (time(9, 0), time(17, 0)),
            1: (time(9, 0), time(17, 0)),
            2: (time(9, 0), time(17, 0)),
            3: (time(9, 0), time(17, 0)),
            4: (time(9, 0), time(17, 0)),
            5: (time(10, 0), time(16, 0)),
        }

        for day in range(7):
            start_end = defaults.get(day)
            StaffWorkingHours.objects.get_or_create(
                staff=staff,
                day_of_week=day,
                defaults={
                    'start_time': start_end[0] if start_end else None,
                    'end_time': start_end[1] if start_end else None,
                }
            )

    def _assign_services_for_business(self, business):
        services = list(Service.objects.filter(
            business=business).order_by('id'))
        if not services:
            return
        staff_members = list(Staff.objects.filter(business=business))
        if not staff_members:
            return

        # Use StaffService to assign services to staff in a round-robin fashion, 2 per staff
        for i, staff in enumerate(staff_members):
            assigned = 0
            for s in services[i::max(1, len(staff_members))]:
                is_primary = assigned == 0
                StaffService.objects.get_or_create(
                    staff=staff,
                    service=s,
                    defaults={'is_primary': is_primary, 'is_online_booking': True,
                              'custom_price': None, 'custom_duration': None}
                )
                assigned += 1
                if assigned >= 2:
                    break
    