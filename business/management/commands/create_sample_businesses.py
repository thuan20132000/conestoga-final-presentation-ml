from django.core.management.base import BaseCommand
from django.utils import timezone
from business.models import (
    BusinessType, Business, OperatingHours, BusinessSettings, BusinessRoles
)
from service.models import ServiceCategory, Service
from staff.models import Staff, StaffService
from payment.models import PaymentMethod


class Command(BaseCommand):
    help = 'Create sample businesses with services, staff, and settings'
    def add_arguments(self, parser):
        # name of the business
        parser.add_argument('--name', type=str, help='Name of the business')

    def handle(self, *args, **options):
        name = options.get('name')

        # Get business types
        self.create_nail_salon(name)

    def create_nail_salon(self, business_name):
        """Create a sample nail salon"""
        business_type = BusinessType.objects.get(name='Nail Salon')
        business, created = Business.objects.get_or_create(
            name=business_name,
            defaults={
                'business_type': business_type,
                'phone_number': '+1-555-0456',
                'email': 'info@luxenails.com',
                'website': 'https://luxenails.com',
                'address': '456 Queen Street',
                'city': 'Toronto',
                'state_province': 'ON',
                'postal_code': 'M5H 2M9',
                'country': 'Canada',
                'description': 'Premium nail salon offering luxury manicures and pedicures',
                'status': 'active'
            }
        )

        return business
