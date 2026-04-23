from django.core.management.base import BaseCommand
from business.models import BusinessType


class Command(BaseCommand):
    help = 'Create default business types'

    def handle(self, *args, **options):
        business_types = [
            {
                'name': 'Hair Salon',
                'description': 'Professional hair styling, cutting, coloring, and treatments',
                'icon': 'scissors'
            },
            {
                'name': 'Nail Salon',
                'description': 'Manicures, pedicures, nail art, and nail treatments',
                'icon': 'hand-paper'
            },
            {
                'name': 'Spa',
                'description': 'Relaxation treatments, massages, facials, and wellness services',
                'icon': 'spa'
            },
            {
                'name': 'Dental Clinic',
                'description': 'Dental care, cleanings, treatments, and oral health services',
                'icon': 'tooth'
            },
            {
                'name': 'Barbershop',
                'description': 'Men\'s haircuts, beard trimming, and grooming services',
                'icon': 'cut'
            },
            {
                'name': 'Beauty Clinic',
                'description': 'Cosmetic treatments, skincare, and aesthetic procedures',
                'icon': 'star'
            },
            {
                'name': 'Massage Therapy',
                'description': 'Therapeutic and relaxation massage services',
                'icon': 'hands'
            },
            {
                'name': 'Tattoo Studio',
                'description': 'Tattoo design, application, and body art services',
                'icon': 'paint-brush'
            },
            {
                'name': 'Eyebrow Studio',
                'description': 'Eyebrow shaping, tinting, microblading, and lash services',
                'icon': 'eye'
            },
            {
                'name': 'Fitness Studio',
                'description': 'Personal training, group classes, and fitness services',
                'icon': 'dumbbell'
            }
        ]

        created_count = 0
        for business_type_data in business_types:
            business_type, created = BusinessType.objects.get_or_create(
                name=business_type_data['name'],
                defaults=business_type_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created business type: {business_type.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Business type already exists: {business_type.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} new business types')
        )
