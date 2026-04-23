from django.db import transaction
from django.utils import timezone
import secrets
import string
from .models import TimeEntry, Staff
from notifications.services import SMSService
from main.common_settings import CALENDAR_LOGIN_URL


class TimeEntryService:

    @staticmethod
    @transaction.atomic
    def clock_in(staff):
        if not staff.is_active:
            raise ValueError("Staff inactive")

        if TimeEntry.objects.filter(staff=staff, clock_out__isnull=True).exists():
            raise ValueError("Already clocked in")

        return TimeEntry.objects.create(
            staff=staff,
            clock_in=timezone.now(),
            status='IN_PROGRESS'
        )

    @staticmethod
    @transaction.atomic
    def clock_out(staff, break_minutes=0):
        try:
            entry = TimeEntry.objects.select_for_update().get(
                staff=staff,
                clock_out__isnull=True
            )
        except TimeEntry.DoesNotExist:
            raise ValueError("No active shift")

        entry.clock_out = timezone.now()
        entry.break_minutes = break_minutes
        entry.calculate_totals()
        entry.status = 'COMPLETED'
        entry.save()
        return entry
    
    @staticmethod
    @transaction.atomic
    def get_time_entry(staff):
        return TimeEntry.objects.get(staff=staff, clock_out__isnull=True)


class StaffCredentialService:
    DEFAULT_PASSWORD_LENGTH = 8
    PASSWORD_CHARS = string.ascii_lowercase
    PASSWORD_DIGITS = string.digits

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        if not phone:
            raise ValueError("Staff phone is required")
        normalized = "".join(char for char in phone if char.isdigit())
        if not normalized:
            raise ValueError("Invalid staff phone number")
        return normalized

    @staticmethod
    def _generate_unique_username(phone: str, staff_id: int | None = None) -> str:
        base_username = StaffCredentialService._normalize_phone(phone)
        username = base_username
        counter = 1
        while Staff.objects.filter(username=username).exclude(pk=staff_id).exists():
            username = f"{base_username}{counter}"
            counter += 1
        return username

    @staticmethod
    def _generate_password(length: int | None = None) -> str:
        length = length or StaffCredentialService.DEFAULT_PASSWORD_LENGTH
        if length < 8:
            length = 8
        chars_part = 'asdf'
        digits_part = ''.join(secrets.choice(StaffCredentialService.PASSWORD_DIGITS) for _ in range(4))
        password = f"{chars_part}{digits_part}"
        return password

    @staticmethod
    def _send_credentials_sms(staff: Staff, username: str, password: str) -> None:
        sms_service = SMSService()
        business_twilio_phone_number = None
        business_id = None
        if staff.business:
            business_id = staff.business_id
            business_twilio_phone_number = getattr(staff.business, "twilio_phone_number", None)

        message = f"{staff.first_name}, your credentials are ready in {staff.business.name}. Username: {username}. Password: {password}."
        message += f"Please login to your account at {CALENDAR_LOGIN_URL}."
        
        result = sms_service.send(
            staff.phone,
            message,
            business_id=business_id,
            business_twilio_phone_number=business_twilio_phone_number
        )
        if not result.ok:
            raise ValueError(result.error or "Failed to send SMS")
        
    @staticmethod
    def _send_staff_code_sms(staff: Staff, staff_code: int) -> None:
        sms_service = SMSService()
        business_twilio_phone_number = None
        business_id = None
        if staff.business:
            business_id = staff.business_id
            business_twilio_phone_number = getattr(staff.business, "twilio_phone_number", None)
        message = f"Hi {staff.first_name}, your security code for {staff.business.name} is {staff_code}. Please logout and login again to use the new code. Thank you!"
        result = sms_service.send(
            staff.phone,
            message,
            business_id=business_id,
            business_twilio_phone_number=business_twilio_phone_number
        )
        if not result.ok:
            raise ValueError(result.error or "Failed to send SMS")

    @staticmethod
    @transaction.atomic
    def create_or_reset_credentials(staff: Staff, send_sms: bool = False) -> dict:
        username = StaffCredentialService._generate_unique_username(staff.phone, staff.pk)
        password = StaffCredentialService._generate_password()
        staff.username = username
        staff.set_password(password)
        staff.save()

        if send_sms:
            StaffCredentialService._send_credentials_sms(staff, username, password)

        return {"username": username, "password": password}

    @staticmethod
    def reset_staff_code(staff: Staff, send_sms: bool = False) -> dict:
        staff.staff_code = secrets.choice(range(10000, 99999))
        while Staff.objects.filter(staff_code=staff.staff_code).exclude(pk=staff.pk).exists():
            staff.staff_code = secrets.choice(range(10000, 99999))
        staff.save()
        if send_sms:
            StaffCredentialService._send_staff_code_sms(staff, staff.staff_code)
        
        return {"staff_code": staff.staff_code}