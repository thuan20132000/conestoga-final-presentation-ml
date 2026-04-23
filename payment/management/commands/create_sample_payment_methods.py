from django.core.management.base import BaseCommand
from business.models import Business
from payment.models import PaymentMethod


class Command(BaseCommand):
    help = 'Create sample payment methods for businesses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='Business ID to create payment methods for (optional)',
        )

    def handle(self, *args, **options):
        business_id = options.get('business_id')
        
        if business_id:
            businesses = Business.objects.filter(id=business_id)
        else:
            businesses = Business.objects.all()

        if not businesses.exists():
            self.stdout.write(
                self.style.ERROR('No businesses found. Please create a business first.')
            )
            return

        payment_methods_data = [
            {
                'name': 'Cash',
                'payment_type': 'cash',
                'processing_fee_percentage': 0,
                'processing_fee_fixed': 0,
                'description': 'Cash payments at the counter',
                'is_default': True,
            },
            {
                'name': 'Credit Card',
                'payment_type': 'credit_card',
                'processing_fee_percentage': 0.029,  # 2.9%
                'processing_fee_fixed': 0.30,
                'description': 'Credit card payments via POS terminal',
            },
            {
                'name': 'Debit Card',
                'payment_type': 'debit_card',
                'processing_fee_percentage': 0.015,  # 1.5%
                'processing_fee_fixed': 0.15,
                'description': 'Debit card payments via POS terminal',
            },
            {
                'name': 'Online Payment',
                'payment_type': 'online',
                'processing_fee_percentage': 0.035,  # 3.5%
                'processing_fee_fixed': 0.30,
                'description': 'Online payments through payment gateway',
            },
            {
                'name': 'Gift Card',
                'payment_type': 'gift_card',
                'processing_fee_percentage': 0,
                'processing_fee_fixed': 0,
                'description': 'Gift card payments',
            },
            {
                'name': 'Bank Transfer',
                'payment_type': 'bank_transfer',
                'processing_fee_percentage': 0.01,  # 1%
                'processing_fee_fixed': 0,
                'description': 'Direct bank transfer payments',
            },
        ]

        total_created = 0
        
        for business in businesses:
            self.stdout.write(f'Creating payment methods for {business.name}...')
            
            # Create payment methods for this business
            for method_data in payment_methods_data:
                method_data_copy = method_data.copy()
                method_data_copy['business'] = business
                
                payment_method, created = PaymentMethod.objects.get_or_create(
                    business=business,
                    name=method_data_copy['name'],
                    defaults=method_data_copy
                )
                
                if created:
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Created: {payment_method.name} ({payment_method.get_payment_type_display()})'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Already exists: {payment_method.name}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {total_created} payment methods across {businesses.count()} businesses'
            )
        )
