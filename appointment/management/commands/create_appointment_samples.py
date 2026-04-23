from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta, time
import random

from business.models import Business
from service.models import Service
from staff.models import Staff, StaffService
from appointment.models import (
    Appointment, Client, AppointmentStatus, AppointmentService, AppointmentReminder
)


class Command(BaseCommand):
    help = 'Create sample appointments, clients, and related data for existing businesses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id', type=int, help='Target a single business id'
        )
        parser.add_argument(
            '--per-business', type=int, default=10,
            help='Number of appointments to create per business (default: 10)'
        )
        parser.add_argument(
            '--days-ahead', type=int, default=30,
            help='How many days ahead to create appointments (default: 30)'
        )
        parser.add_argument(
            '--clear-existing', action='store_true',
            help='Remove existing appointments and clients for targeted businesses before creating'
        )
        parser.add_argument(
            '--include-past', action='store_true',
            help='Include some past appointments (completed/cancelled)'
        )

    def handle(self, *args, **options):
        business_id = options.get('business_id')
        per_business = options.get('per_business')
        days_ahead = options.get('days_ahead')
        clear_existing = options.get('clear_existing')
        include_past = options.get('include_past')
        
        if business_id:
            businesses = Business.objects.filter(id=business_id)
        else:
            businesses = Business.objects.all()

        if not businesses.exists():
            self.stdout.write(self.style.WARNING('No businesses found'))
            return

        # Ensure appointment statuses exist
        self._ensure_appointment_statuses()

        for business in businesses:
            with transaction.atomic():
                if clear_existing:
                    self._clear_for_business(business)
                
                created_appointments = self._create_appointments_for_business(
                    business, per_business, days_ahead, include_past)
                
                self.stdout.write(self.style.SUCCESS(
                    f"Business '{business.name}': created {created_appointments} appointments"
                ))

    def _clear_for_business(self, business):
        """Clear existing appointments and clients for a business"""
        # Delete in order to respect foreign key constraints
        AppointmentReminder.objects.filter(appointment__business=business).delete()
        AppointmentService.objects.filter(appointment__business=business).delete()
        Appointment.objects.filter(business=business).delete()
        # Note: We don't delete clients as they might be referenced by other businesses

    def _ensure_appointment_statuses(self):
        """Ensure all appointment statuses exist"""
        statuses = [
            ('scheduled', 'Scheduled', '#007bff', 1),
            ('confirmed', 'Confirmed', '#28a745', 2),
            ('in_progress', 'In Progress', '#ffc107', 3),
            ('completed', 'Completed', '#6c757d', 4),
            ('cancelled', 'Cancelled', '#dc3545', 5),
            ('no_show', 'No Show', '#6f42c1', 6),
            ('rescheduled', 'Rescheduled', '#fd7e14', 7),
        ]
        
        for status_key, status_name, color, sort_order in statuses:
            AppointmentStatus.objects.get_or_create(
                name=status_key,
                defaults={
                    'description': f'Appointment status: {status_name}',
                    'color': color,
                    'is_active': True,
                    'sort_order': sort_order,
                }
            )

    def _create_appointments_for_business(self, business, per_business, days_ahead, include_past):
        """Create sample appointments for a business"""
        services = list(Service.objects.filter(business=business, is_active=True))
        if not services:
            self.stdout.write(self.style.WARNING(f"No active services found for business '{business.name}'"))
            return 0

        staff_members = list(Staff.objects.filter(business=business, is_active=True))
        if not staff_members:
            self.stdout.write(self.style.WARNING(f"No active staff found for business '{business.name}'"))
            return 0

        # Get available staff services
        staff_services = {}
        for staff in staff_members:
            staff_services[staff] = list(StaffService.objects.filter(
                staff=staff, service__business=business, is_active=True
            ).select_related('service'))

        # Create sample clients
        clients = self._create_sample_clients(business, per_business)

        created_count = 0
        now = timezone.now()
        
        for i in range(per_business):
            client = random.choice(clients)
            service = random.choice(services)
            
            # Find staff who can provide this service
            available_staff = []
            for staff, staff_services_list in staff_services.items():
                if any(ss.service == service for ss in staff_services_list):
                    available_staff.append(staff)
            
            if not available_staff:
                # If no staff is specifically assigned to this service, use any staff
                staff = random.choice(staff_members)
            else:
                staff = random.choice(available_staff)

            # Determine appointment date and time
            if include_past and i < per_business // 3:  # 1/3 of appointments are in the past
                days_offset = random.randint(-30, -1)
                appointment_date = now.date() + timedelta(days=days_offset)
            else:
                days_offset = random.randint(1, days_ahead)
                appointment_date = now.date() + timedelta(days=days_offset)

            # Generate appointment time based on business hours (9 AM - 6 PM)
            start_hour = random.randint(9, 17)
            start_minute = random.choice([0, 15, 30, 45])
            start_time = time(start_hour, start_minute)
            
            # Calculate end time based on service duration
            service_duration = service.duration_minutes or 60
            end_time = (datetime.combine(appointment_date, start_time) + 
                       timedelta(minutes=service_duration)).time()

            # Determine status based on appointment date
            if appointment_date < now.date():
                # Past appointments
                status_key = random.choice(['completed', 'cancelled', 'no_show'])
            elif appointment_date == now.date():
                # Today's appointments
                status_key = random.choice(['scheduled', 'confirmed', 'in_progress'])
            else:
                # Future appointments
                status_key = random.choice(['scheduled', 'confirmed'])

            status = AppointmentStatus.objects.get(name=status_key)

            # Calculate pricing
            service_price = service.price
            tax_rate = getattr(business.settings, 'tax_rate', 0.13) if hasattr(business, 'settings') else 0.13
            tax_amount = service_price * tax_rate
            total_price = service_price + tax_amount

            # Create appointment
            appointment = Appointment(
                business=business,
                client=client,
                service=service,
                staff=staff,
                appointment_date=appointment_date,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=service_duration,
                status=status,
                notes=self._generate_appointment_notes(),
                internal_notes=self._generate_internal_notes() if random.choice([True, False]) else '',
                service_price=service_price,
                tax_amount=tax_amount,
                total_price=total_price,
                is_paid=random.choice([True, False]) if status_key == 'completed' else False,
                payment_method=random.choice(['cash', 'credit_card', 'debit_card']) if status_key == 'completed' else None,
                booking_source=random.choice(['online', 'phone', 'ai_receptionist', 'staff']),
                confirmed_at=now if status_key in ['confirmed', 'in_progress', 'completed'] else None,
                completed_at=now if status_key == 'completed' else None,
                cancelled_at=now if status_key == 'cancelled' else None,
            )
            
            # For past appointments, bypass the date validation
            if appointment_date < now.date():
                # Create with a future date first, then update to past date
                appointment.appointment_date = now.date() + timedelta(days=1)
                appointment.save()
                # Update to the actual past date
                Appointment.objects.filter(id=appointment.id).update(appointment_date=appointment_date)
                appointment.refresh_from_db()
            else:
                appointment.save()

            # Create appointment service (additional services)
            if random.choice([True, False]):  # 50% chance of additional services
                additional_service = random.choice([s for s in services if s != service])
                AppointmentService.objects.create(
                    appointment=appointment,
                    service=additional_service,
                    staff=staff,
                    is_requested=True,
                    custom_price=additional_service.price,
                    custom_duration=additional_service.duration_minutes,
                    is_active=True,
                )

            # Create appointment reminders for future appointments
            if status_key in ['scheduled', 'confirmed'] and appointment_date > now.date():
                self._create_appointment_reminders(appointment)

            created_count += 1

        return created_count

    def _create_sample_clients(self, business, count):
        """Create sample clients for the business"""
        sample_clients = [
            ('John', 'Smith', 'john.smith@email.com', '+1-555-0101'),
            ('Sarah', 'Johnson', 'sarah.j@email.com', '+1-555-0102'),
            ('Michael', 'Brown', 'mike.brown@email.com', '+1-555-0103'),
            ('Emily', 'Davis', 'emily.davis@email.com', '+1-555-0104'),
            ('David', 'Wilson', 'david.w@email.com', '+1-555-0105'),
            ('Jessica', 'Miller', 'jessica.m@email.com', '+1-555-0106'),
            ('Christopher', 'Garcia', 'chris.g@email.com', '+1-555-0107'),
            ('Amanda', 'Martinez', 'amanda.m@email.com', '+1-555-0108'),
            ('Matthew', 'Anderson', 'matt.a@email.com', '+1-555-0109'),
            ('Ashley', 'Taylor', 'ashley.t@email.com', '+1-555-0110'),
            ('James', 'Thomas', 'james.t@email.com', '+1-555-0111'),
            ('Jennifer', 'Jackson', 'jennifer.j@email.com', '+1-555-0112'),
            ('Robert', 'White', 'robert.w@email.com', '+1-555-0113'),
            ('Linda', 'Harris', 'linda.h@email.com', '+1-555-0114'),
            ('William', 'Martin', 'william.m@email.com', '+1-555-0115'),
            ('Patricia', 'Thompson', 'patricia.t@email.com', '+1-555-0116'),
            ('Richard', 'Moore', 'richard.m@email.com', '+1-555-0117'),
            ('Barbara', 'Young', 'barbara.y@email.com', '+1-555-0118'),
            ('Joseph', 'Allen', 'joseph.a@email.com', '+1-555-0119'),
            ('Elizabeth', 'King', 'elizabeth.k@email.com', '+1-555-0120'),
        ]

        clients = []
        for i, (first_name, last_name, email, phone) in enumerate(sample_clients[:count]):
            # Create unique email for each business
            business_email = email.replace('@email.com', f'@{business.name.replace(" ", "").lower()}.com')
            client, created = Client.objects.get_or_create(
                email=business_email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone,
                    'date_of_birth': timezone.now().date() - timedelta(days=random.randint(18*365, 65*365)),
                    'notes': random.choice([
                        'Regular customer',
                        'Prefers morning appointments',
                        'Allergic to certain products',
                        'VIP customer',
                        'New client',
                        '',
                        '',
                    ])
                }
            )
            clients.append(client)

        return clients

    def _generate_appointment_notes(self):
        """Generate random appointment notes"""
        notes_options = [
            'Client requested specific styling',
            'First time visit',
            'Follow-up appointment',
            'Special occasion',
            'Client mentioned sensitive skin',
            'Regular maintenance appointment',
            'Client wants to try new service',
            'Consultation appointment',
            '',
            '',
            '',
        ]
        return random.choice(notes_options)

    def _generate_internal_notes(self):
        """Generate random internal notes"""
        internal_notes_options = [
            'Client was very satisfied with previous service',
            'Client prefers quiet environment',
            'Client mentioned budget concerns',
            'VIP client - provide extra attention',
            'Client has mobility issues',
            'Client prefers specific staff member',
            'Client mentioned referral from friend',
            'Client is interested in package deals',
            '',
            '',
        ]
        return random.choice(internal_notes_options)

    def _create_appointment_reminders(self, appointment):
        """Create appointment reminders for future appointments"""
        reminder_types = ['email', 'sms']
        reminder_hours = [24, 2]  # 24 hours and 2 hours before
        
        for reminder_type, hours_before in zip(reminder_types, reminder_hours):
            # Create timezone-aware datetime
            appointment_datetime = timezone.datetime.combine(
                appointment.appointment_date,
                appointment.start_time
            )
            appointment_datetime = timezone.make_aware(appointment_datetime)
            
            scheduled_time = appointment_datetime - timedelta(hours=hours_before)
            
            AppointmentReminder.objects.create(
                appointment=appointment,
                reminder_type=reminder_type,
                scheduled_time=scheduled_time,
                is_sent=False,
                is_delivered=False,
            )
