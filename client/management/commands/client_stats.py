from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from client.models import Client, ClientPreference


class Command(BaseCommand):
    help = 'Display client statistics and analytics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='Filter stats for specific business ID'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed statistics'
        )

    def handle(self, *args, **options):
        business_id = options.get('business_id')
        detailed = options['detailed']
        
        # Base queryset
        clients = Client.objects.all()
        if business_id:
            clients = clients.filter(primary_business_id=business_id)
        
        self.stdout.write(self.style.SUCCESS('=== CLIENT STATISTICS ===\n'))
        
        # Basic statistics
        total_clients = clients.count()
        active_clients = clients.filter(is_active=True).count()
        inactive_clients = total_clients - active_clients
        vip_clients = clients.filter(is_vip=True).count()
        
        self.stdout.write(f'Total Clients: {total_clients}')
        self.stdout.write(f'Active Clients: {active_clients}')
        self.stdout.write(f'Inactive Clients: {inactive_clients}')
        self.stdout.write(f'VIP Clients: {vip_clients}')
        self.stdout.write('')
        
        # Recent activity
        now = timezone.now()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)
        
        new_clients_7_days = clients.filter(created_at__gte=last_7_days).count()
        new_clients_30_days = clients.filter(created_at__gte=last_30_days).count()
        
        self.stdout.write('Recent Activity:')
        self.stdout.write(f'  New clients (last 7 days): {new_clients_7_days}')
        self.stdout.write(f'  New clients (last 30 days): {new_clients_30_days}')
        self.stdout.write('')
        
        # Clients by business
        if not business_id:  # Only show if not filtering by business
            self.stdout.write('Clients by Business:')
            business_stats = (
                clients.values('primary_business__name')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            
            for stat in business_stats:
                business_name = stat['primary_business__name'] or 'No Business'
                count = stat['count']
                self.stdout.write(f'  {business_name}: {count}')
            self.stdout.write('')
        
        # Contact method preferences
        self.stdout.write('Preferred Contact Methods:')
        contact_methods = (
            clients.values('preferred_contact_method')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        for method in contact_methods:
            method_name = method['preferred_contact_method']
            count = method['count']
            percentage = (count / total_clients * 100) if total_clients > 0 else 0
            self.stdout.write(f'  {method_name}: {count} ({percentage:.1f}%)')
        self.stdout.write('')
        
        # Geographic distribution
        if detailed:
            self.stdout.write('Geographic Distribution:')
            cities = (
                clients.exclude(city__isnull=True)
                .exclude(city='')
                .values('city')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )
            
            for city in cities:
                self.stdout.write(f'  {city["city"]}: {city["count"]}')
            self.stdout.write('')
            
            # States/Provinces
            states = (
                clients.exclude(state_province__isnull=True)
                .exclude(state_province='')
                .values('state_province')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )
            
            for state in states:
                self.stdout.write(f'  {state["state_province"]}: {state["count"]}')
            self.stdout.write('')
        
        # Preference statistics
        if detailed:
            self.stdout.write('Client Preferences:')
            preference_types = (
                ClientPreference.objects.filter(client__in=clients)
                .values('preference_type')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            
            for pref_type in preference_types:
                self.stdout.write(f'  {pref_type["preference_type"]}: {pref_type["count"]}')
            self.stdout.write('')
        
        # Age distribution
        if detailed:
            self.stdout.write('Age Distribution:')
            age_ranges = [
                ('18-25', Q(date_of_birth__gte=now.date().replace(year=now.year-25), date_of_birth__lt=now.date().replace(year=now.year-18))),
                ('26-35', Q(date_of_birth__gte=now.date().replace(year=now.year-35), date_of_birth__lt=now.date().replace(year=now.year-26))),
                ('36-45', Q(date_of_birth__gte=now.date().replace(year=now.year-45), date_of_birth__lt=now.date().replace(year=now.year-36))),
                ('46-55', Q(date_of_birth__gte=now.date().replace(year=now.year-55), date_of_birth__lt=now.date().replace(year=now.year-46))),
                ('56-65', Q(date_of_birth__gte=now.date().replace(year=now.year-65), date_of_birth__lt=now.date().replace(year=now.year-56))),
                ('65+', Q(date_of_birth__lt=now.date().replace(year=now.year-65))),
            ]
            
            for age_range, age_filter in age_ranges:
                count = clients.filter(age_filter).count()
                percentage = (count / total_clients * 100) if total_clients > 0 else 0
                self.stdout.write(f'  {age_range}: {count} ({percentage:.1f}%)')
            self.stdout.write('')

        self.stdout.write(self.style.SUCCESS('Statistics completed!'))
