from django.db import transaction, models
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import time, date, timedelta
import calendar
from decimal import Decimal
import json
import os
import logging
import hashlib
from pathlib import Path
from typing import Any
import requests
from pgvector.django import CosineDistance
from .models import Business, BusinessSettings, BusinessRoles, OperatingHours, BusinessOnlineBooking, BusinessType
from service.models import ServiceCategory, Service
from staff.models import Staff, StaffSocialAccount, StaffService
from payment.models import PaymentMethod, Payment
from client.models import Client
from appointment.models import Appointment
from review.models import Review
from webpush.models import Group, PushInformation
from main.utils import get_business_managers_group_name
import csv
from main.common_settings import ONLINE_BOOKING_URL
from staff.services import StaffCredentialService
from subscription.models import BusinessSubscription, SubscriptionStatus, SubscriptionPlan
from payment.models import PaymentStatusType
from appointment.models import AppointmentStatusType
from notifications.services import EmailService

logger = logging.getLogger(__name__)


class BusinessInitializerService:
    """Base class for business initializer services"""
    service_csv_path = "dummy/services_by_salon_2026-01-26.csv"
    category_csv_path = "dummy/service_categories_by_salon_2026-01-26.csv"
    def __init__(self, business):
        self.business = business
        self.category_mapping = {}

    def initialize(self):
        with transaction.atomic():
            self._create_business_settings()
            self._create_business_roles()
            self._create_operating_hours()
            self._create_payment_methods()
            self._create_business_managers_group()
            self._create_online_booking()
            self._create_service_categories()
            self._create_services()
            self._create_staff()
            self._create_manager()

    def _create_business_settings(self):
        """Create default business settings"""
        settings_data = {
            'business': self.business,
            'advance_booking_days': self.settings_data.get('advance_booking_days', 30),
            'min_advance_booking_hours': self.settings_data.get('min_advance_booking_hours', 2),
            'max_advance_booking_days': self.settings_data.get('max_advance_booking_days', 90),
            'time_slot_interval': self.settings_data.get('time_slot_interval', 15),
            'buffer_time_minutes': self.settings_data.get('buffer_time_minutes', 0),
            'send_reminder_emails': self.settings_data.get('send_reminder_emails', True),
            'send_reminder_sms': False,
            'reminder_hours_before': self.settings_data.get('reminder_hours_before', 2),
            'send_confirmation_sms': False,
            'currency': self.settings_data.get('currency', "CAD"),
            'tax_rate': self.settings_data.get('tax_rate', 0.13),
            'require_payment_advance': False,
            'allow_online_booking': True,
            'require_client_phone': True,
            'require_client_email': False,
            'auto_confirm_appointments': False,
            'timezone': self.settings_data.get('timezone', "America/Toronto"),
        }
        settings = BusinessSettings.objects.create(**settings_data)
        return settings
        

    def _create_business_roles(self):
        """Create default business roles"""
        defaults_roles = [
            {
                "name": "Technician",
                "description": "Technician of the business",
            },
            {
                "name": "Manager",
                "description": "Manager of the business",
            },
            {
                "name": "Receptionist",
                "description": "Receptionist of the business",
            },
            {
                "name": "Owner",
                "description": "Owner of the business",
            },
        ]
        for role in defaults_roles:
            BusinessRoles.objects.create(business=self.business, **role)

    def _create_staff(self):
        """Create default staff members"""
        technician_role = BusinessRoles.objects.get(name='Technician', business=self.business)
        
        defaults_staff = [
            {
                'first_name': 'John',
                'last_name': 'Nguyen',
                'email': 'john.nguyen@example.com',
                'phone': '1234567890',
                'role': technician_role,
            },
            {
                'first_name': 'Tony',
                'last_name': 'Le',
                'email': 'tony.le@example.com',
                'phone': '1234567891',
                'role': technician_role,
            },
        ]
        for staff in defaults_staff:
            Staff.objects.create(business=self.business, **staff)

    def _create_manager(self,):
        """Create default managers"""
        manager_role = BusinessRoles.objects.get(name='Manager', business=self.business)
        defaults_managers = {   
                'first_name': 'Lisa',
                'last_name': 'Tran',
                'email': 'lisa.tran@example.com',
                'phone': '1234567892',
                'role': manager_role,
            }
        manager = Staff.objects.create(business=self.business, **defaults_managers)
        manager.set_password('!Matkhau@123')
        manager.save()

    def _create_operating_hours(self):
        """Create default operating hours for each day of the week"""
        for day in range(7):
            OperatingHours.objects.create(
                business=self.business,
                day_of_week=day,
                is_open=True,
                open_time=time(9, 30),
                close_time=time(19, 30),
            )

    def _create_payment_methods(self):
        """Create default payment methods"""
        defaults_payment_methods = [
            {
                'name': 'Cash',
                'payment_type': 'cash',
                'description': 'Cash payment',
                'is_active': True,
            },
            {
                'name': 'Credit Card',
                'payment_type': 'credit_card',
                'description': 'Credit Card payment',
                'is_active': False,
            },
            {
                'name': 'Debit Card',
                'payment_type': 'debit_card',
                'description': 'Debit Card payment',
                'is_active': True,
            },
            {
                'name': 'Online Payment',
                'payment_type': 'online',
                'description': 'Online payment',
                'is_active': False,
            },
            {
                'name': 'Gift Card',
                'payment_type': 'gift_card',
                'description': 'Gift Card payment',
                'is_active': True,
            },
            {
                'name': 'Bank Transfer',
                'payment_type': 'bank_transfer',
                'description': 'Bank Transfer payment',
                'is_active': True,
            },
        ]
        for payment_method in defaults_payment_methods:
            PaymentMethod.objects.create(business=self.business, **payment_method)

    def _create_business_managers_group(self):
        """Create business managers group for webpush notifications"""
        Group.objects.create(name=get_business_managers_group_name(self.business.id))

    def _create_online_booking(self):
        """Create default online booking configuration"""
        business_description = self.business.description if self.business.description else 'Online Booking'
        business_policy = 'Booking policy/terms shown to clients'
        BusinessOnlineBooking.objects.create(
            business=self.business,
            name=self.business.name,
            description=business_description,
            policy=business_policy,
            interval_minutes=self.business.settings.time_slot_interval,
            buffer_time_minutes=self.business.settings.buffer_time_minutes,
            is_active=True,
            shareable_link=f'{ONLINE_BOOKING_URL}/?business_id={self.business.id}',
        )

    def _create_service_categories(self):
        """Create default service categories"""
        base_dir = Path(__file__).resolve().parent
        csv_path = base_dir / self.category_csv_path
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header row
            for row in reader:
                if not row:
                    continue
                category = ServiceCategory.objects.create(
                    business=self.business,
                    name=row[2],
                    color_code=row[3],
                    sort_order=row[0],
                    is_online_booking=True,
                    is_active=True,
                )
                self.category_mapping[category.name] = category

    def _create_services(self):
        """Create default services"""
        base_dir = Path(__file__).resolve().parent
        csv_path = base_dir / self.service_csv_path
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header row
            for row in reader:
                if not row:
                    continue
                category = self.category_mapping.get(row[5])
                if not category:
                    category = None
                Service.objects.create(
                    business=self.business,
                    category=category,
                    name=row[2],
                    duration_minutes=row[4],
                    price=row[3],
                    is_active=True,
                    sort_order=row[0],
                    is_online_booking=True,
                )

class BellebizBusinessInitializerService(BusinessInitializerService):
    def __init__(self, business):
        self.business = business
        self._category_mapping = {}  # Maps serviceTypeId to category name

    def initialize(self):
        with transaction.atomic():
            self._create_business_settings()
            self._create_business_roles()
            self._create_service_categories()
            self._create_services()
            self._create_staff()
            self._create_operating_hours()
            self._create_payment_methods()
            self._create_business_managers_group()
            self._create_online_booking()


    def _create_service_categories(self):
        """Create default service categories from JSON file"""
        # Get the path to the JSON file
        base_dir = Path(__file__).resolve().parent
        json_path = base_dir / 'dummy' / 'nailicious-categories.json'
        
        # Load categories from JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            categories_data = json.load(f)
        
        # Store category mapping for services (serviceTypeId -> category object)
        self._category_mapping = {}
        
        # Create categories, filtering only active ones
        for cat_data in categories_data:
            if cat_data.get('isActive', True):  # Only create active categories
                category = ServiceCategory.objects.create(
                    business=self.business,
                    name=cat_data.get('name', ''),
                    description=cat_data.get('description') or '',
                    color_code=cat_data.get('colorCode') or '',
                    sort_order=cat_data.get('orderBy', 0),
                    is_online_booking=cat_data.get('isOnlineBooking', True),
                    is_active=cat_data.get('isActive', True),
                )
                # Map serviceTypeId to category object for service creation
                service_type_id = str(cat_data.get('id', ''))
                self._category_mapping[service_type_id] = category

    def _create_services(self):
        """Create default services from JSON file"""
        # Get the path to the JSON file
        base_dir = Path(__file__).resolve().parent
        json_path = base_dir / 'dummy' / 'nailicious-services.json'
        
        # Load services from JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            services_data = json.load(f)
        
        # Create services
        for service_data in services_data:
            # Skip if service is deleted or not active
            if service_data.get('isDeleted', False) or not service_data.get('isActive', True):
                continue
            
            # Get the category from serviceTypeId
            service_type_id = str(service_data.get('serviceTypeId', ''))
            category = self._category_mapping.get(service_type_id)
            
            if not category:
                # Skip if category not found
                continue
            
            # Convert price to Decimal
            price_str = service_data.get('price', '0')
            try:
                price = Decimal(str(price_str))
            except (ValueError, TypeError):
                price = Decimal('0')
            
            # Get duration
            duration = service_data.get('duration', 0)
            if not duration or duration <= 0:
                duration = 30  # Default duration
            
            # Create the service
            Service.objects.create(
                business=self.business,
                category=category,
                name=service_data.get('name', ''),
                description=service_data.get('description') or '',
                duration_minutes=duration,
                price=price,
                is_active=service_data.get('isActive', True),
                sort_order=service_data.get('orderBy', 0),
                is_online_booking=service_data.get('isOnlineBooking', True),
            )



class BusinessRegisterService(BusinessInitializerService):
    """Service for registering a new business"""
    service_csv_path = "dummy/services_by_salon_2026-01-26.csv"
    category_csv_path = "dummy/service_categories_by_salon_2026-01-26.csv"
    
    
    def __init__(self, business: dict, owner: dict, business_type_name: str, settings: dict):
        super().__init__(business)
        self.business_data = business
        self.owner_data = owner
        self.settings_data = settings
        business_type_name = str(business_type_name).title()
        if business_type_name == 'Hair Salon':
            print("Creating hair salon services and categories")
            self.service_csv_path = "dummy/hair_salon_service2026.csv"
            self.category_csv_path = "dummy/hair_salon_category2026.csv"
        
       
    def initialize(self, send_sms=True):
        with transaction.atomic():
            self.business = self._create_business()
            self._create_business_settings()
            self._create_business_roles()
            self._create_operating_hours()
            self._create_payment_methods()
            self._create_business_managers_group()
            self._create_online_booking()
            self._create_service_categories()
            self._create_services()
            self._subscribe_free_trial()
            self._create_staff()
            owner = self._create_owner(send_sms=send_sms)
            self.owner = owner

        self._send_welcome_email(owner)
        return owner

    def _send_welcome_email(self, owner):
        if not owner.email:
            return
        from django.conf import settings as django_settings
        dashboard_url = getattr(django_settings, 'DASHBOARD_URL', 'https://partners.bookngon.com/dashboard/')
        context = {
            'owner_name': owner.first_name or owner.email,
            'business_name': self.business.name,
            'dashboard_url': dashboard_url,
        }
        EmailService().send_async(
            subject=f"Welcome to Bookngon – {self.business.name} is ready!",
            to_email=owner.email,
            template='emails/business_welcome.html',
            context=context,
        )
            
            
    def _create_business(self):
        """Create default business"""
        business_data = {
            'name': self.business_data.get('name'),
            'business_type': self.business_data.get('business_type'),
            'phone_number': self.business_data.get('phone_number','+15550001'),
            'email': self.business_data.get('email','info1@luxenails.com'),
            'website': self.business_data.get('website', 'https://bookngon.com'),
            'address': self.business_data.get('address', '456 Queen Street'),
            'city': self.business_data.get('city', 'Toronto'),
            'state_province': self.business_data.get('state_province', 'ON'),
            'postal_code': self.business_data.get('postal_code', 'M5H 2M9'),
            'country': self.business_data.get('country', 'Canada'),
            'currency': self.business_data.get('currency', 'CAD'),
            'description': self.business_data.get('description', 'Description of the business'),
            'logo': self.business_data.get('logo'),
            'google_review_url': self.business_data.get('google_review_url', 'https://www.google.com/search?q=123+Main+St+Toronto+ON'),
            'status': self.business_data.get('status', 'active'),
        }
        business = Business.objects.create(**business_data)
        return business
            
    def _create_owner(self, send_sms=True):
        """Create default owner"""
        owner_role = BusinessRoles.objects.get(name='Owner', business=self.business)
        owner = Staff.objects.create(business=self.business, role=owner_role, **self.owner_data)
        
        if owner.phone:
            StaffCredentialService.create_or_reset_credentials(owner, send_sms=send_sms)
        return owner

    def _subscribe_free_trial(self):
        """Subscribe to free trial"""
        subscription = BusinessSubscription.objects.create(
            business=self.business,
            plan=SubscriptionPlan.objects.get(name='Free Trial', is_active=True),
            status=SubscriptionStatus.TRIALING,
        )
        return subscription


class BusinessGoogleAuthService:
    """Handles Google OAuth registration and login for business owners."""

    @staticmethod
    def _verify_google_token(google_id_token: str) -> dict:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        from django.conf import settings

        google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        if not google_client_id:
            raise ValueError('Google login is not configured.')

        try:
            idinfo = id_token.verify_oauth2_token(
                google_id_token,
                google_requests.Request(),
                google_client_id,
                clock_skew_in_seconds=10,
            )
        except ValueError as e:
            raise ValueError('Invalid Google token.')

        email = idinfo.get('email')
        if not email or not idinfo.get('email_verified'):
            raise ValueError('Google account email is not verified.')

        return idinfo

    @staticmethod
    def register(google_id_token: str, business_data: dict, business_type_name: str, settings_data: dict) -> Staff:
        """
        Register a new business + owner via Google OAuth.
        Owner identity is derived from the verified Google token.
        No SMS credentials are sent.
        """
        idinfo = BusinessGoogleAuthService._verify_google_token(google_id_token)

        provider_user_id = idinfo['sub']
        if StaffSocialAccount.objects.filter(
            provider='google', provider_user_id=provider_user_id
        ).exists():
            raise ValueError('A business is already registered with this Google account.')

        email = idinfo['email']
        if Staff.objects.filter(email__iexact=email, is_deleted=False).exists():
            raise ValueError('An account with this email already exists.')

        owner_data = {
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'email': email,
        }

        service = BusinessRegisterService(business_data, owner_data, business_type_name, settings_data)
        owner = service.initialize(send_sms=False)
        owner.set_unusable_password()
        owner.save(update_fields=['password'])

        StaffSocialAccount.objects.create(
            staff=owner,
            provider='google',
            provider_user_id=provider_user_id,
            email=email,
        )
        return owner

    @staticmethod
    def login(google_id_token: str) -> Staff:
        """
        Authenticate a business owner via Google OAuth.
        Looks up Staff by the provider identity stored in StaffSocialAccount,
        with a lazy backfill fallback to email lookup for owners who registered
        before the StaffSocialAccount table was introduced.
        """
        idinfo = BusinessGoogleAuthService._verify_google_token(google_id_token)
        provider_user_id = idinfo['sub']
        email = idinfo['email']

        social_account = StaffSocialAccount.objects.select_related('staff').filter(
            provider='google',
            provider_user_id=provider_user_id,
        ).first()

        if social_account:
            staff = social_account.staff
            if email and social_account.email != email:
                social_account.email = email
                social_account.save(update_fields=['email', 'updated_at'])
        else:
            staff = Staff.objects.filter(
                email__iexact=email, is_deleted=False, is_active=True
            ).first()
            if not staff:
                raise ValueError('No account found for this Google email. Please register first.')
            StaffSocialAccount.objects.create(
                staff=staff,
                provider='google',
                provider_user_id=provider_user_id,
                email=email,
            )

        if staff.is_deleted or not staff.is_active:
            raise ValueError('This account is no longer active.')

        return staff


class BusinessFacebookAuthService:
    """Handles Facebook OAuth registration and login for business owners."""

    @staticmethod
    def _verify_facebook_token(facebook_access_token: str) -> dict:
        """
        Verify the Facebook access token via Graph API.
        Returns {id, first_name, last_name, email} — email may be None when
        the user did not grant the email permission.
        """
        import requests as http_requests
        from django.conf import settings

        app_id = getattr(settings, 'FACEBOOK_APP_ID', '')
        app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', '')
        if not app_id or not app_secret:
            raise ValueError('Facebook login is not configured.')

        try:
            inspect_resp = http_requests.get(
                'https://graph.facebook.com/debug_token',
                params={
                    'input_token': facebook_access_token,
                    'access_token': f'{app_id}|{app_secret}',
                },
                timeout=10,
            )
            inspect_resp.raise_for_status()
            inspect_data = inspect_resp.json().get('data', {})
        except Exception:
            raise ValueError('Failed to inspect Facebook token.')

        if not inspect_data.get('is_valid') or inspect_data.get('app_id') != app_id:
            raise ValueError('Facebook token is not valid for this application.')

        granted_scopes = inspect_data.get('scopes', [])

        fields = 'id,first_name,last_name'
        if 'email' in granted_scopes:
            fields += ',email'

        try:
            response = http_requests.get(
                'https://graph.facebook.com/me',
                params={'fields': fields, 'access_token': facebook_access_token},
                timeout=10,
            )
            response.raise_for_status()
            fb_data = response.json()
        except Exception:
            raise ValueError('Failed to verify Facebook token.')

        if 'error' in fb_data or not fb_data.get('id'):
            raise ValueError('Invalid Facebook token.')

        email = fb_data.get('email') if isinstance(fb_data.get('email'), str) else None
        return {
            'id': fb_data['id'],
            'first_name': fb_data.get('first_name', ''),
            'last_name': fb_data.get('last_name', ''),
            'email': email,
        }

    @staticmethod
    def register(facebook_access_token: str, business_data: dict, business_type_name: str, settings_data: dict) -> Staff:
        """
        Register a new business + owner via Facebook OAuth.
        Owner identity is derived from the verified Facebook token.
        No SMS credentials are sent.
        """
        fb_data = BusinessFacebookAuthService._verify_facebook_token(facebook_access_token)

        if StaffSocialAccount.objects.filter(
            provider='facebook', provider_user_id=fb_data['id']
        ).exists():
            raise ValueError('A business is already registered with this Facebook account.')

        email = fb_data['email']
        if email and Staff.objects.filter(email__iexact=email, is_deleted=False).exists():
            raise ValueError('An account with this email already exists.')

        owner_data = {
            'first_name': fb_data['first_name'],
            'last_name': fb_data['last_name'],
            'email': email or '',
        }

        service = BusinessRegisterService(business_data, owner_data, business_type_name, settings_data)
        owner = service.initialize(send_sms=False)
        owner.set_unusable_password()
        owner.save(update_fields=['password'])

        StaffSocialAccount.objects.create(
            staff=owner,
            provider='facebook',
            provider_user_id=fb_data['id'],
            email=email,
        )
        return owner

    @staticmethod
    def login(facebook_access_token: str) -> Staff:
        """
        Authenticate a business owner via Facebook OAuth.
        Looks up Staff by the provider identity stored in StaffSocialAccount.
        """
        fb_data = BusinessFacebookAuthService._verify_facebook_token(facebook_access_token)

        social_account = StaffSocialAccount.objects.select_related('staff').filter(
            provider='facebook',
            provider_user_id=fb_data['id'],
        ).first()

        if not social_account:
            raise ValueError('No account found for this Facebook identity. Please register first.')

        staff = social_account.staff
        if staff.is_deleted or not staff.is_active:
            raise ValueError('This account is no longer active.')

        new_email = fb_data['email']
        if new_email and social_account.email != new_email:
            social_account.email = new_email
            social_account.save(update_fields=['email', 'updated_at'])

        return staff


class DashboardService:
    """Service for computing business dashboard KPI metrics."""

    def __init__(self, business: Business, from_date: date, to_date: date):
        self.business = business
        self.from_date = from_date
        self.to_date = to_date
        period_days = (to_date - from_date).days + 1
        self.prev_to_date = from_date - timedelta(days=1)
        self.prev_from_date = self.prev_to_date - timedelta(days=period_days - 1)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_dashboard_data(self) -> dict:
        return {
            'total_appointments': self._total_appointments(),
            'total_revenue': self._total_revenue(),
            'total_customers': self._total_customers(),
            'average_rating': self._average_rating(),
            'completed_payments': self._completed_payments(),
            'active_staff': self._active_staff(),
            'todays_appointments': self._todays_appointments(),
            'appointments_by_status': self._appointments_by_status(),
            'booking_sources': self._booking_sources(),
            'revenue_by_payment_method': self._revenue_by_payment_method(),
            'total_tips': self._total_tips(),
            'average_ticket_value': self._average_ticket_value(),
            'cancellation_rate': self._cancellation_rate(),
            'no_show_rate': self._no_show_rate(),
            'staff_performance': self._staff_performance(),
            'daily_trends': self._daily_trends(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _change_percentage(self, current, previous):
        """Return % change vs previous period, or None if no prior data."""
        if previous is None or previous == 0:
            return None
        return round(((current - previous) / previous) * 100, 1)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _total_appointments(self) -> dict:
        base = dict(business=self.business,status__in=[
            AppointmentStatusType.SCHEDULED,
            AppointmentStatusType.IN_SERVICE,
            AppointmentStatusType.CHECKED_IN,
            AppointmentStatusType.CANCELLED,
        ], is_deleted=False)
        current = Appointment.objects.filter(
            appointment_date__range=(self.from_date, self.to_date), **base
        ).count()
        previous = Appointment.objects.filter(
            appointment_date__range=(self.prev_from_date, self.prev_to_date), **base
        ).count()
        return {
            'count': current,
            'change_percentage': self._change_percentage(current, previous),
        }

    def _total_revenue(self) -> dict:
        current_amount = (
            Payment.objects.filter(
                created_at__date__range=(self.from_date, self.to_date), 
                business=self.business,
                status=PaymentStatusType.COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )
        previous_amount = (
            Payment.objects.filter(
                created_at__date__range=(self.prev_from_date, self.prev_to_date), 
                business=self.business,
                status=PaymentStatusType.COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )
        return {
            'amount': float(current_amount),
            'change_percentage': self._change_percentage(
                float(current_amount), float(previous_amount)
            ),
        }

    def _total_customers(self) -> dict:
        base = dict(primary_business=self.business, is_active=True, is_deleted=False)
        current = Client.objects.filter(**base).count()
        previous = Client.objects.filter(
            created_at__date__range=(self.prev_from_date, self.prev_to_date), **base
        ).count()
        week_ago = timezone.now() - timedelta(days=7)
        new_this_week = Client.objects.filter(created_at__gte=week_ago, **base).count()
        return {
            'count': current,
            'new_this_week': new_this_week,
            'change_percentage': self._change_percentage(current, previous),
        }

    def _average_rating(self) -> dict:
        qs = Review.objects.filter(
            appointment__business=self.business,
            is_active=True,
            is_deleted=False,
            reviewed_at__date__range=(self.from_date, self.to_date),
        )
        result = qs.aggregate(avg=Avg('rating'), total=Count('id'))
        avg = result['avg']
        return {
            'value': round(float(avg), 1) if avg is not None else None,
            'review_count': result['total'],
        }

    def _completed_payments(self) -> dict:
        count = Payment.objects.filter(
            business=self.business,
            status=PaymentStatusType.COMPLETED,
            created_at__date__range=(self.from_date, self.to_date),
        ).count()
        return {'count': count}

    def _active_staff(self) -> dict:
        count = Staff.objects.filter(
            business=self.business,
            is_active=True,
            is_deleted=False,
        ).count()
        return {'count': count}

    def _todays_appointments(self) -> list:
        from appointment.models import Appointment
        today = date.today()
        appts = (
            Appointment.objects
            .filter(business=self.business, appointment_date=today, status__in=[
                AppointmentStatusType.SCHEDULED,
                AppointmentStatusType.IN_SERVICE,
                AppointmentStatusType.CHECKED_IN,
                AppointmentStatusType.CANCELLED,
                AppointmentStatusType.NO_SHOW,
            ], is_deleted=False)
            .select_related('client')
            .prefetch_related('appointment_services__service')
            .order_by('start_at')
        )
        result = []
        for appt in appts:
            client = appt.client
            if client:
                client_name = f"{client.first_name or ''} {client.last_name or ''}".strip() or None
            else:
                client_name = None
            services = [
                as_.service.name
                for as_ in appt.appointment_services.all()
                if as_.service and not as_.is_deleted
            ]
            result.append({
                'id': appt.id,
                'status': appt.status,
                'client_name': client_name,
                'start_at': appt.start_at,
                'booking_source': appt.booking_source,
                'services': services,
            })
        return result


class BusinessKnowledgeCollectorService:
    """Collect business domain data into canonical RAG chunks."""

    def __init__(self, business: Business):
        self.business = business

    def collect(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        chunks.extend(self._collect_business_profile())
        chunks.extend(self._collect_hours())
        chunks.extend(self._collect_services())
        chunks.extend(self._collect_service_categories())
        chunks.extend(self._collect_staff())
        chunks.extend(self._collect_policies())
        chunks.extend(self._collect_ai_prompt())
        return chunks

    def _collect_business_profile(self) -> list[dict[str, Any]]:
        content = (
            f"Business name: {self.business.name}\n"
            f"Description: {self.business.description or 'N/A'}\n"
            f"Phone: {self.business.phone_number or 'N/A'}\n"
            f"Email: {self.business.email or 'N/A'}\n"
            f"Website: {self.business.website or 'N/A'}\n"
            f"Address: {self.business.address or 'N/A'}\n"
            f"City: {self.business.city or 'N/A'}\n"
            f"State/Province: {self.business.state_province or 'N/A'}\n"
            f"Postal Code: {self.business.postal_code or 'N/A'}\n"
            f"Country: {self.business.country or 'N/A'}"
        )
        return [
            {
                "source_type": "business",
                "source_id": str(self.business.id),
                "title": f"{self.business.name} profile",
                "content": content,
                "metadata": {"business_id": str(self.business.id)},
            }
        ]

    def _collect_hours(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        hours = OperatingHours.objects.filter(business=self.business).order_by("day_of_week")
        day_names = dict(OperatingHours.DAY_CHOICES)
        for item in hours:
            day_name = day_names.get(item.day_of_week, str(item.day_of_week))
            if item.is_open:
                content = (
                    f"{day_name}: Open {item.open_time or 'N/A'} to {item.close_time or 'N/A'}. "
                    f"Break enabled: {'yes' if item.is_break_time else 'no'}. "
                    f"Break window: {item.break_start_time or 'N/A'} to {item.break_end_time or 'N/A'}."
                )
            else:
                content = f"{day_name}: Closed."

            chunks.append(
                {
                    "source_type": "hours",
                    "source_id": str(item.id),
                    "title": f"Operating hours - {day_name}",
                    "content": content,
                    "metadata": {"day_of_week": item.day_of_week, "is_open": item.is_open},
                }
            )
        return chunks

    def _collect_services(self) -> list[dict[str, Any]]:
        print("Collecting services...")
        chunks: list[dict[str, Any]] = []
        services = Service.objects.filter(business=self.business, is_active=True).select_related("category")
        for service in services:
            print(f"Service: {service.name}")
            category_name = service.category.name if service.category else "Uncategorized"
            content = (
                f"Service: {service.name}\n"
                f"Category: {category_name}\n"
                f"Description: {service.description or 'N/A'}\n"
                f"Duration minutes: {service.duration_minutes}\n"
                f"Price: {service.price}\n"
                f"Online booking enabled: {'yes' if service.is_online_booking else 'no'}"
            )
            chunks.append(
                {
                    "source_type": "service",
                    "source_id": str(service.id),
                    "title": service.name,
                    "content": content,
                    "metadata": {
                        "category_id": service.category_id,
                        "is_online_booking": service.is_online_booking,
                    },
                }
            )
        return chunks

    def _collect_service_categories(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        categories = ServiceCategory.objects.filter(business=self.business, is_active=True)
        for category in categories:
            content = (
                f"Service category: {category.name}\n"
                f"Description: {category.description or 'N/A'}\n"
                f"Sort order: {category.sort_order}"
            )
            chunks.append(
                {
                    "source_type": "service_category",
                    "source_id": str(category.id),
                    "title": category.name,
                    "content": content,
                    "metadata": {"sort_order": category.sort_order},
                }
            )
        return chunks

    def _collect_staff(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        staffs = Staff.objects.filter(business=self.business, is_deleted=False).select_related("role")
        for staff in staffs:
            services = StaffService.objects.filter(staff=staff, is_active=True).select_related("service")
            service_names = [s.service.name for s in services if s.service]
            content = (
                f"Staff name: {staff.get_full_name() or staff.username}\n"
                f"Role: {staff.role.name if staff.role else 'N/A'}\n"
                f"Phone: {staff.phone or 'N/A'}\n"
                f"Email: {staff.email or 'N/A'}\n"
                f"Specialties: {', '.join(service_names) if service_names else 'N/A'}"
            )
            chunks.append(
                {
                    "source_type": "staff",
                    "source_id": str(staff.id),
                    "title": staff.get_full_name() or staff.username,
                    "content": content,
                    "metadata": {"is_active": staff.is_active},
                }
            )
        return chunks

    def _collect_policies(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        online_booking = BusinessOnlineBooking.objects.filter(business=self.business).first()
        if not online_booking:
            return chunks

        policy_content = online_booking.policy or ""
        if not policy_content.strip():
            return chunks

        chunks.append(
            {
                "source_type": "policy",
                "source_id": str(online_booking.id),
                "title": f"{self.business.name} booking policy",
                "content": policy_content,
                "metadata": {"business_online_booking_id": str(online_booking.id)},
            }
        )
        return chunks

    def _collect_ai_prompt(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        from receptionist.models import AIConfiguration

        ai_config = AIConfiguration.objects.filter(
            business=self.business,
            status="active",
        ).order_by("-updated_at").first()
        if not ai_config or not ai_config.prompt:
            return chunks

        chunks.append(
            {
                "source_type": "ai_prompt",
                "source_id": str(ai_config.id),
                "title": f"{self.business.name} AI prompt",
                "content": ai_config.prompt,
                "metadata": {"ai_name": ai_config.ai_name, "language": ai_config.language},
            }
        )
        return chunks


class BusinessKnowledgeService:
    """Embed and store/retrieve business knowledge chunks."""

    EMBEDDING_MODEL = "text-embedding-3-small"
    MAX_CHUNK_LENGTH = 4000
    MAX_CHUNKS_PER_REINDEX = 500
    ALLOWED_SOURCE_TYPES = {
        "business",
        "service",
        "service_category",
        "staff",
        "policy",
        "hours",
        "banner",
        "ai_prompt",
    }

    def __init__(self, business: Business):
        self.business = business
        from receptionist.models import KnowledgeChunk

        self.chunk_model = KnowledgeChunk

    @staticmethod
    def _content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _embed_text(self, text: str) -> list[float]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing")

        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.EMBEDDING_MODEL, "input": text},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        if not data:
            raise ValueError("Embedding response did not include data")
        return data[0]["embedding"]

    def reindex(self, reason: str, source_types: list[str] | None = None) -> dict[str, Any]:
        collector = BusinessKnowledgeCollectorService(self.business)
        all_chunks = collector.collect()
        all_chunks = all_chunks[: self.MAX_CHUNKS_PER_REINDEX]
        if source_types:
            invalid = set(source_types) - self.ALLOWED_SOURCE_TYPES
            if invalid:
                raise ValueError(f"Unsupported source_types: {sorted(invalid)}")
            all_chunks = [chunk for chunk in all_chunks if chunk["source_type"] in source_types]

        candidate_keys = {(chunk["source_type"], chunk["source_id"]) for chunk in all_chunks}
        print(f"Candidate keys: {candidate_keys}")
        print(f"Source types: {source_types}")
        # print(f"Reason: {reason}")
        print(f"Business: {self.business}")
        existing = self.chunk_model.objects.filter(business=self.business)
        print(f"Existing: {existing}")
        if source_types:
            existing = existing.filter(source_type__in=source_types)
        print(f"Existing: {existing}")
        existing_map = {(obj.source_type, obj.source_id): obj for obj in existing}
        created = 0
        updated = 0
        skipped = 0

        for chunk in all_chunks:
            if len(chunk["content"]) > self.MAX_CHUNK_LENGTH:
                chunk["content"] = chunk["content"][: self.MAX_CHUNK_LENGTH]
            key = (chunk["source_type"], chunk["source_id"])
            existing_chunk = existing_map.get(key)
            content_hash = self._content_hash(chunk["content"])

            metadata = dict(chunk.get("metadata") or {})
            metadata["content_hash"] = content_hash
            metadata["reindex_reason"] = reason

            if existing_chunk and existing_chunk.metadata.get("content_hash") == content_hash:
                skipped += 1
                continue

            embedding = self._embed_text(chunk["content"])

            if existing_chunk:
                existing_chunk.title = chunk["title"]
                existing_chunk.content = chunk["content"]
                existing_chunk.embedding = embedding
                existing_chunk.metadata = metadata
                existing_chunk.save(
                    update_fields=["title", "content", "embedding", "metadata", "updated_at"]
                )
                updated += 1
            else:
                print(f"Creating chunk: {chunk}")
                chunk = self.chunk_model.objects.create(
                    business=self.business,
                    source_type=chunk["source_type"],
                    source_id=chunk["source_id"],
                    title=chunk["title"],
                    content=chunk["content"],
                    embedding=embedding,
                    metadata=metadata,
                )
                print(f"Created chunk: {chunk}")
                created += 1

        stale_qs = existing.exclude(
            models.Q(
                pk__in=[
                    existing_map[key].pk
                    for key in candidate_keys
                    if key in existing_map
                ]
            )
        )
        if source_types:
            stale_qs = stale_qs.filter(source_type__in=source_types)

        deleted = stale_qs.count()
        if deleted > len(all_chunks):
            print(f"Deleting {deleted} stale chunks")
            stale_qs.delete()
            print(f"Deleted {deleted} stale chunks")
            
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total_candidates": len(all_chunks),
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_types: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        print(f"Searching knowledge for query: {query}")
        print(f"Source types: {source_types}")
        print(f"Score threshold: {score_threshold}")
        if source_types:
            invalid = set(source_types) - self.ALLOWED_SOURCE_TYPES
            if invalid:
                raise ValueError(f"Unsupported source_types: {sorted(invalid)}")
        top_k = max(1, min(top_k, 10))
        query_embedding = self._embed_text(query)
        qs = self.chunk_model.objects.filter(business=self.business)
        if source_types:
            qs = qs.filter(source_type__in=source_types)

        qs = qs.annotate(distance=CosineDistance("embedding", query_embedding)).order_by("distance")[:top_k]
        results: list[dict[str, Any]] = []
        for item in qs:
            score = 1 - float(item.distance)
            if score_threshold is not None and score < score_threshold:
                continue
            results.append(
                {
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "title": item.title,
                    "content": item.content,
                    "score": round(score, 6),
                    "metadata": item.metadata,
                }
            )
        return results

    def _appointments_by_status(self) -> dict:
        from appointment.models import Appointment, AppointmentStatusType
        base_qs = Appointment.objects.filter(
            business=self.business,
            appointment_date__range=(self.from_date, self.to_date),
            is_deleted=False,
        )
        return {
            status_val: base_qs.filter(status=status_val).count()
            for status_val, _ in AppointmentStatusType.choices
        }

    def _booking_sources(self) -> dict:
        from appointment.models import Appointment, BookingSourceType
        base_qs = Appointment.objects.filter(
            business=self.business,
            appointment_date__range=(self.from_date, self.to_date),
            is_deleted=False,
            status__in=[
                AppointmentStatusType.SCHEDULED,
                AppointmentStatusType.IN_SERVICE,
                AppointmentStatusType.CHECKED_IN,
                AppointmentStatusType.CANCELLED,
                AppointmentStatusType.NO_SHOW,
            ],
        )
        return {
            source_val: base_qs.filter(booking_source=source_val).count()
            for source_val, _ in BookingSourceType.choices
        }

    def _revenue_by_payment_method(self) -> list:
        rows = (
            Payment.objects
            .filter(
                business=self.business,
                status=PaymentStatusType.COMPLETED,
                created_at__date__range=(self.from_date, self.to_date),
            )
            .values('payment_method_type')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        return [
            {'method': row['payment_method_type'], 'amount': float(row['total'] or 0)}
            for row in rows
        ]

    def _total_tips(self) -> float:
        from appointment.models import AppointmentService
        total = (
            AppointmentService.objects
            .filter(
                appointment__business=self.business,
                appointment__appointment_date__range=(self.from_date, self.to_date),
                appointment__is_deleted=False,
                is_deleted=False,
            )
            .aggregate(total=Sum('tip_amount'))['total']
        )
        return float(total or 0)

    def _average_ticket_value(self) -> float:
        completed_count = Payment.objects.filter(
            business=self.business,
            status=PaymentStatusType.COMPLETED,
            created_at__date__range=(self.from_date, self.to_date),
        ).count()
        if completed_count == 0:
            return 0.0
        total_revenue = (
            Payment.objects
            .filter(
                business=self.business,
                status=PaymentStatusType.COMPLETED,
                created_at__date__range=(self.from_date, self.to_date),
            )
            .aggregate(total=Sum('amount'))['total'] or Decimal('0')
        )
        return round(float(total_revenue) / completed_count, 2)

    def _cancellation_rate(self) -> float:
        from appointment.models import Appointment
        total = Appointment.objects.filter(
            business=self.business,
            appointment_date__range=(self.from_date, self.to_date),
            is_deleted=False,
        ).count()
        if total == 0:
            return 0.0
        cancelled = Appointment.objects.filter(
            business=self.business,
            appointment_date__range=(self.from_date, self.to_date),
            is_deleted=False,
            status='cancelled',
        ).count()
        return round((cancelled / total) * 100, 1)

    def _no_show_rate(self) -> float:
        from appointment.models import Appointment
        total = Appointment.objects.filter(
            business=self.business,
            appointment_date__range=(self.from_date, self.to_date),
            is_deleted=False,
        ).count()
        if total == 0:
            return 0.0
        no_shows = Appointment.objects.filter(
            business=self.business,
            appointment_date__range=(self.from_date, self.to_date),
            is_deleted=False,
            status='no_show',
        ).count()
        return round((no_shows / total) * 100, 1)

    def _staff_performance(self) -> list:
        staff_members = Staff.objects.filter(
            business=self.business,
            is_active=True,
            is_deleted=False,
            role__name__in=['Technician', 'Stylist'],
        )
        result = []
        for staff in staff_members:
            service_qs = staff.appointment_services.filter(
                appointment__business=self.business,
                appointment__appointment_date__range=(self.from_date, self.to_date),
                appointment__is_deleted=False,
                is_active=True,
                is_deleted=False,
            )
            
            completed_service_qs = service_qs.filter(
                appointment__status=AppointmentStatusType.CHECKED_OUT,
            )
            service_sales_amount = (
                completed_service_qs.aggregate(total=Sum('custom_price'))['total'] or Decimal('0')
            )
            
            total_completed_services = completed_service_qs.count()
            total_appointment_services_requested = service_qs.filter(
                is_staff_request=True
            ).values('appointment').distinct().count()
            
            result.append({
                'staff_id': staff.id,
                'name': f"{staff.first_name or ''}".strip(),
                'total_completed_services': total_completed_services,
                'total_services_requested': total_appointment_services_requested,
                'sales': float(service_sales_amount),
            })
        result.sort(key=lambda x: x['sales'], reverse=True)
        return result

    def _daily_trends(self) -> list:
        from appointment.models import Appointment
        current = self.from_date
        result = []
        while current <= self.to_date:
            appt_count = Appointment.objects.filter(
                business=self.business,
                appointment_date=current,
                status__in=[
                    AppointmentStatusType.SCHEDULED,
                    AppointmentStatusType.IN_SERVICE,
                    AppointmentStatusType.CHECKED_IN,
                ],
                is_deleted=False,
            ).count()
            daily_revenue = (
                Payment.objects
                .filter(
                    business=self.business,
                    status=PaymentStatusType.COMPLETED,
                    created_at__date=current,
                )
                .aggregate(total=Sum('amount'))['total'] or Decimal('0')
            )
            result.append({
                'date': current,
                'appointments': appt_count,
                'revenue': float(daily_revenue),
            })
            current += timedelta(days=1)
        
        return result