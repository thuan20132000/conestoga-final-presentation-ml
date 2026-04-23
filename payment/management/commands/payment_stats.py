from django.core.management.base import BaseCommand
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from payment.models import Payment, PaymentStatus
from business.models import Business


class Command(BaseCommand):
    help = 'Display payment statistics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='Business ID to get stats for (optional)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to include in stats (default: 30)',
        )

    def handle(self, *args, **options):
        business_id = options.get('business_id')
        days = options.get('days')
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Base queryset
        payments = Payment.objects.filter(created_at__date__range=[start_date, end_date])
        
        if business_id:
            payments = payments.filter(business_id=business_id)
            business = Business.objects.get(id=business_id)
            self.stdout.write(
                self.style.SUCCESS(f'Payment Statistics for {business.name}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Overall Payment Statistics (Last {days} days)')
            )
        
        self.stdout.write('=' * 60)
        
        # Basic statistics
        total_payments = payments.count()
        total_amount = payments.aggregate(total=Sum('amount'))['total'] or 0
        total_processing_fees = payments.aggregate(total=Sum('processing_fee'))['total'] or 0
        net_amount = payments.aggregate(total=Sum('net_amount'))['total'] or 0
        avg_payment = payments.aggregate(avg=Avg('amount'))['avg'] or 0
        
        self.stdout.write(f'Total Payments: {total_payments:,}')
        self.stdout.write(f'Total Amount: ${total_amount:,.2f}')
        self.stdout.write(f'Total Processing Fees: ${total_processing_fees:,.2f}')
        self.stdout.write(f'Net Amount: ${net_amount:,.2f}')
        self.stdout.write(f'Average Payment: ${avg_payment:,.2f}')
        self.stdout.write('')
        
        # Status breakdown
        self.stdout.write(self.style.WARNING('Payment Status Breakdown:'))
        status_stats = payments.values('status__name').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-count')
        
        for stat in status_stats:
            status_name = stat['status__name']
            count = stat['count']
            amount = stat['total_amount'] or 0
            percentage = (count / total_payments * 100) if total_payments > 0 else 0
            
            self.stdout.write(
                f'  {status_name.title()}: {count:,} payments (${amount:,.2f}) - {percentage:.1f}%'
            )
        
        self.stdout.write('')
        
        # Payment method breakdown
        self.stdout.write(self.style.WARNING('Payment Method Breakdown:'))
        method_stats = payments.values('payment_method__name', 'payment_method__payment_type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-count')
        
        for stat in method_stats:
            method_name = stat['payment_method__name']
            method_type = stat['payment_method__payment_type']
            count = stat['count']
            amount = stat['total_amount'] or 0
            percentage = (count / total_payments * 100) if total_payments > 0 else 0
            
            self.stdout.write(
                f'  {method_name} ({method_type}): {count:,} payments (${amount:,.2f}) - {percentage:.1f}%'
            )
        
        self.stdout.write('')
        
        # Daily breakdown
        self.stdout.write(self.style.WARNING('Daily Breakdown (Last 7 days):'))
        daily_stats = payments.filter(
            created_at__date__gte=end_date.date() - timedelta(days=7)
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('day')
        
        for stat in daily_stats:
            day = stat['day']
            count = stat['count']
            amount = stat['total_amount'] or 0
            
            self.stdout.write(f'  {day}: {count:,} payments (${amount:,.2f})')
        
        # Business breakdown (if not filtering by business)
        if not business_id:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Business Breakdown:'))
            business_stats = payments.values('business__name').annotate(
                count=Count('id'),
                total_amount=Sum('amount')
            ).order_by('-total_amount')
            
            for stat in business_stats:
                business_name = stat['business__name']
                count = stat['count']
                amount = stat['total_amount'] or 0
                
                self.stdout.write(f'  {business_name}: {count:,} payments (${amount:,.2f})')
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'Statistics generated for {days} days ending {end_date.date()}')
        )
