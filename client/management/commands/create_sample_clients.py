from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import random
from faker import Faker

from client.models import Client, ClientPreference
from business.models import Business


class Command(BaseCommand):
    help = 'Create sample clients for testing and development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of clients to create (default: 50)'
        )
        parser.add_argument(
            '--business-id',
            type=int,
            help='Specific business ID to associate clients with'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing sample clients before creating new ones'
        )

    def handle(self, *args, **options):
        count = options['count']
        business_id = options.get('business_id')
        clear_existing = options['clear']
        
        fake = Faker()
        
        if clear_existing:
            self.stdout.write('Clearing existing sample clients...')
            Client.objects.all().delete()
        
        # Get businesses
        businesses = Business.objects.all()
        if not businesses.exists():
            self.stdout.write(
                self.style.ERROR('No businesses found. Please create businesses first.')
            )
            return
        
        if business_id:
            try:
                businesses = Business.objects.filter(id=business_id)
                if not businesses.exists():
                    self.stdout.write(
                        self.style.ERROR(f'Business with ID {business_id} not found.')
                    )
                    return
            except Business.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Business with ID {business_id} not found.')
                )
                return
        
        self.stdout.write(f'Creating {count} sample clients...')
        
        created_count = 0
        for i in range(count):
            try:
                # Generate client data
                first_name = fake.first_name()
                last_name = fake.last_name()
                email = fake.email()
                phone = fake.phone_number()[:20]  # Limit to 20 chars
                
                # Random date of birth (18-80 years old)
                age = random.randint(18, 80)
                date_of_birth = fake.date_of_birth(minimum_age=age, maximum_age=age)
                
                # Address information
                address_line1 = fake.street_address()
                address_line2 = fake.secondary_address() if random.choice([True, False]) else ''
                city = fake.city()
                state_province = fake.state()
                postal_code = fake.postcode()
                country = fake.country()
                
                # Emergency contact
                emergency_contact_name = fake.name() if random.choice([True, False]) else ''
                emergency_contact_phone = fake.phone_number()[:20] if emergency_contact_name else ''
                emergency_contact_relation = random.choice([
                    'Spouse', 'Parent', 'Child', 'Sibling', 'Friend', 'Other'
                ]) if emergency_contact_name else ''
                
                # Preferences
                preferred_contact_method = random.choice(['email', 'phone', 'sms'])
                notes = fake.text(max_nb_chars=200) if random.choice([True, False]) else ''
                medical_notes = fake.text(max_nb_chars=200) if random.choice([True, False]) else ''
                
                # Business association
                primary_business = random.choice(businesses)
                
                # Status
                is_active = random.choice([True, True, True, False])  # 75% active
                is_vip = random.choice([True, False]) if is_active else False
                
                # Create client
                client = Client.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone=phone,
                    date_of_birth=date_of_birth,
                    address_line1=address_line1,
                    address_line2=address_line2 or None,
                    city=city,
                    state_province=state_province,
                    postal_code=postal_code,
                    country=country,
                    emergency_contact_name=emergency_contact_name or None,
                    emergency_contact_phone=emergency_contact_phone or None,
                    emergency_contact_relation=emergency_contact_relation or None,
                    preferred_contact_method=preferred_contact_method,
                    notes=notes or None,
                    medical_notes=medical_notes or None,
                    primary_business=primary_business,
                    is_active=is_active,
                    is_vip=is_vip
                )
                
                # Create some preferences for the client
                self._create_client_preferences(client, fake)
                
                created_count += 1
                
                if created_count % 10 == 0:
                    self.stdout.write(f'Created {created_count} clients...')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating client {i+1}: {str(e)}')
                )
                continue
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} sample clients')
        )

    def _create_client_preferences(self, client, fake):
        """Create sample preferences for a client"""
        preference_types = ['service', 'staff', 'time', 'communication', 'other']
        
        # Create 1-3 random preferences
        num_preferences = random.randint(1, 3)
        for _ in range(num_preferences):
            pref_type = random.choice(preference_types)
            
            if pref_type == 'service':
                preference_key = random.choice(['preferred_service_type', 'avoid_service_type'])
                preference_value = random.choice(['Haircut', 'Coloring', 'Styling', 'Facial', 'Massage'])
            elif pref_type == 'staff':
                preference_key = 'preferred_staff_gender'
                preference_value = random.choice(['Male', 'Female', 'No Preference'])
            elif pref_type == 'time':
                preference_key = random.choice(['preferred_time_of_day', 'preferred_day_of_week'])
                if preference_key == 'preferred_time_of_day':
                    preference_value = random.choice(['Morning', 'Afternoon', 'Evening'])
                else:
                    preference_value = random.choice(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
            elif pref_type == 'communication':
                preference_key = 'reminder_frequency'
                preference_value = random.choice(['1 day before', '2 days before', '1 week before', 'No reminders'])
            else:
                preference_key = fake.word()
                preference_value = fake.sentence()
            
            ClientPreference.objects.create(
                client=client,
                preference_type=pref_type,
                preference_key=preference_key,
                preference_value=preference_value
            )
