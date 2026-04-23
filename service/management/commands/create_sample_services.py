from django.core.management.base import BaseCommand
from django.db import transaction

from business.models import Business, BusinessType
from service.models import ServiceCategory, Service


class Command(BaseCommand):
    help = 'Create sample service categories and services for businesses'

    def add_arguments(self, parser):
        parser.add_argument('--business-id', type=int, help='Target a single business id')
        parser.add_argument('--clear-existing', action='store_true', help='Remove existing categories/services first')

    def handle(self, *args, **options):
        business_id = options.get('business_id')
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
                    Service.objects.filter(business=business).delete()
                    ServiceCategory.objects.filter(business=business).delete()

                self._create_for_business(business)
                self.stdout.write(self.style.SUCCESS(f"Business '{business.name}': services ensured"))

    def _create_for_business(self, business):
        btype: BusinessType = business.business_type
        type_name = (btype.name or '').lower()
        if 'hair' in type_name:
            self._seed_hair_salon(business)
        elif 'nail' in type_name:
            self._seed_nail_salon(business)
        elif 'spa' in type_name:
            self._seed_spa(business)
        elif 'dental' in type_name or 'dent' in type_name:
            self._seed_dental(business)
        else:
            self._seed_generic(business)

    def _ensure_category(self, business, name, description, sort_order):
        category, _ = ServiceCategory.objects.get_or_create(
            business=business,
            name=name,
            defaults={
                'description': description,
                'sort_order': sort_order,
                'is_active': True,
            }
        )
        return category

    def _ensure_service(self, business, category, name, duration, price):
        Service.objects.get_or_create(
            business=business,
            name=name,
            defaults={
                'category': category,
                'description': '',
                'duration_minutes': duration,
                'price': price,
                'is_active': True,
                'requires_staff': True,
                'max_capacity': 1,
            }
        )

    def _seed_hair_salon(self, business):
        cut = self._ensure_category(business, 'Hair Cuts', 'Professional haircuts', 1)
        color = self._ensure_category(business, 'Hair Coloring', 'Color services', 2)
        treatment = self._ensure_category(business, 'Hair Treatments', 'Treatments', 3)

        self._ensure_service(business, cut, "Women's Cut & Style", 60, 85.00)
        self._ensure_service(business, cut, "Men's Cut", 30, 45.00)
        self._ensure_service(business, color, 'Full Color', 120, 150.00)
        self._ensure_service(business, color, 'Highlights', 90, 120.00)
        self._ensure_service(business, treatment, 'Deep Conditioning', 45, 65.00)

    def _seed_nail_salon(self, business):
        mani = self._ensure_category(business, 'Manicures', 'Nail care', 1)
        pedi = self._ensure_category(business, 'Pedicures', 'Foot care', 2)
        art = self._ensure_category(business, 'Nail Art', 'Creative designs', 3)

        self._ensure_service(business, mani, 'Classic Manicure', 45, 35.00)
        self._ensure_service(business, mani, 'Gel Manicure', 60, 50.00)
        self._ensure_service(business, pedi, 'Classic Pedicure', 60, 45.00)
        self._ensure_service(business, art, 'Nail Art Design', 30, 25.00)

    def _seed_spa(self, business):
        massage = self._ensure_category(business, 'Massage Therapy', 'Massage and body treatments', 1)
        facial = self._ensure_category(business, 'Facial Treatments', 'Skincare services', 2)

        self._ensure_service(business, massage, 'Swedish Massage', 60, 120.00)
        self._ensure_service(business, massage, 'Deep Tissue Massage', 60, 130.00)
        self._ensure_service(business, facial, 'Classic Facial', 60, 100.00)

    def _seed_dental(self, business):
        general = self._ensure_category(business, 'General Dentistry', 'Routine dental care', 1)
        cosmetic = self._ensure_category(business, 'Cosmetic Dentistry', 'Aesthetic treatments', 2)

        self._ensure_service(business, general, 'Dental Cleaning', 60, 120.00)
        self._ensure_service(business, general, 'Dental Exam', 30, 80.00)
        self._ensure_service(business, cosmetic, 'Teeth Whitening', 90, 300.00)

    def _seed_generic(self, business):
        general = self._ensure_category(business, 'General', 'General services', 1)
        self._ensure_service(business, general, 'Consultation', 30, 0.00)


