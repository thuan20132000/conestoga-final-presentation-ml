from appointment.models import AppointmentService, Appointment, AppointmentStatusType
from datetime import datetime
from payment.models import PaymentMethodType
from staff.models import StaffService, StaffWorkingHours, StaffWorkingHoursOverride, StaffOffDay, Staff
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from notifications.models import Notification
from notifications.services import NotificationDispatcher, EmailService, SMSService
from business.models import BusinessSettings
import logging
from main.utils import get_business_managers_group_name
from main.common_settings import ONLINE_BOOKING_URL
from django.db.models import QuerySet, Sum, Count, Value, DateField, F, Q
from client.models import Client
from payment.models import Payment, PaymentStatusType
from dateutil import parser
from main.utils import get_reminder_schedule_name

logger = logging.getLogger(__name__)
class BusinessBookingService:
    def __init__(self, business_id, interval_minutes=15):
        self.business_id = business_id
        self.interval_minutes = interval_minutes

    def _check_staff_services(self, staff_id, service_ids):
        try:
            staff_services = StaffService.objects.filter(
                staff__id=staff_id,
                service__in=service_ids,
                is_active=True
            )

            if staff_services.count() != len(service_ids) or staff_services.count() == 0:
                return False
            return True
        except Exception as e:
            raise Exception(f"Error checking staff services: {e}")
    
    def get_client_minimum_booking_duration(self, client_id, duration):
        try:
            client = Client.objects.get(id=client_id)
            if client.minimum_booking_duration_minutes > int(duration):
                return int(client.minimum_booking_duration_minutes)
            return int(duration)
        except Exception as e:
            return int(duration)

    def _get_staff_working_hours(self, staff_id, appointment_date):
        try:
            # convert appointment_date 2025-11-21 to weekday
            weekday = datetime.strptime(
                appointment_date, '%Y-%m-%d').weekday()

            override = self._get_staff_working_hours_override(staff_id, appointment_date)

            if override:
                return override

            working_hours = StaffWorkingHours.objects.filter(
                staff__id=staff_id,
                day_of_week=weekday,
                is_working=True,
                staff__is_online_booking_allowed=True,
            ).first()

            if not working_hours:
                return False

            return working_hours
        except Exception as e:
            raise Exception(f"Error getting staff working hours: {e}")

    def _get_staff_working_hours_override(self, staff_id, appointment_date):
        try:
            override = StaffWorkingHoursOverride.objects.filter(
                staff__id=staff_id,
                staff__business_id=self.business_id,
                date=appointment_date,
                staff__is_online_booking_allowed=True,
                is_working=True,
            ).first()
            return override
        except Exception as e:
            raise Exception(f"Error getting staff working hours override: {e}")

    def _check_staff_off_days(self, staff_id, appointment_date):
        try:
            day_offs = StaffOffDay.objects.filter(
                staff__id=staff_id,
                start_date__lte=appointment_date,
                end_date__gte=appointment_date
            )
            if day_offs.exists():
                return True
            return False
        except Exception as e:
            raise Exception(f"Error checking staff off days: {e}")

    def _generate_time_slots(
        self,
        current_time,
        next_time,
        service_duration,
        staff_id,
        interval_minutes,
        appointment_date
    ):
        time_slots = []
        appointment_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        while (current_time + service_duration) <= next_time:
            service_end_time = current_time + service_duration

            start_time = (datetime.min + current_time).strftime('%H:%M')
            end_time = (datetime.min + service_end_time).strftime('%H:%M')
            
            start_time = timezone.make_aware(datetime.strptime(start_time, '%H:%M'))
            start_time = start_time.replace(
                year=appointment_date.year, 
                month=appointment_date.month, 
                day=appointment_date.day
            )    
                                             
            end_time = timezone.make_aware(datetime.strptime(end_time, '%H:%M'))
            end_time = end_time.replace(
                year=appointment_date.year, 
                month=appointment_date.month, 
                day=appointment_date.day
            )
            
            time_slots.append({
                'start_time': start_time,
                'end_time': end_time,
                'staff_id': staff_id,
            })
            current_time = current_time + \
                timedelta(minutes=interval_minutes)

        return time_slots

    def get_staff_time_slots(self, staff_id, service_ids, appointment_date, service_duration):
        try:
            # Check if business is open on the date
            # operating_hours = self._get_operating_hours()
            time_slots = []
            interval_minutes = self.interval_minutes

            if self._check_staff_off_days(staff_id, appointment_date):
                return time_slots

            # Check if staff provides the service and is active
            if not self._check_staff_services(staff_id, service_ids):
                return time_slots

            staff_working_hours = self._get_staff_working_hours(
                staff_id, 
                appointment_date,
            )

            if not staff_working_hours:
                return time_slots

            # convert time to timezone aware
            queryset = AppointmentService.objects.filter(
                staff_id=staff_id,
                is_active=True,
                appointment__appointment_date=appointment_date,
                appointment__is_active=True
            ).exclude(
                appointment__status=AppointmentStatusType.CANCELLED.value,
            )

            time_zone = timezone.get_current_timezone()

            # sort queryset by start_at
            booked_time_slots = queryset.order_by('start_at')

            staff_working_start_time = timedelta(
                hours=staff_working_hours.start_time.hour,
                minutes=staff_working_hours.start_time.minute
            )
            staff_working_end_time = timedelta(
                hours=staff_working_hours.end_time.hour,
                minutes=staff_working_hours.end_time.minute
            )

            current_time = staff_working_start_time
            total_service_duration = timedelta(minutes=int(service_duration))
            for booked_time_slot in booked_time_slots:
                booked_start_time = booked_time_slot.start_at.astimezone(
                    time_zone).time()
                booked_end_time = booked_time_slot.end_at.astimezone(
                    time_zone).time()
                booked_start_time = timedelta(
                    hours=booked_start_time.hour, minutes=booked_start_time.minute)
                booked_end_time = timedelta(
                    hours=booked_end_time.hour, minutes=booked_end_time.minute)

                latest_start_time = booked_start_time - total_service_duration

                if booked_start_time < staff_working_start_time and booked_end_time > staff_working_start_time:
                    current_time = booked_end_time
                    continue

                if booked_start_time > staff_working_end_time:
                    break

                # If there's enough time before the booking, generate slots
                if current_time <= latest_start_time:
                    slots = self._generate_time_slots(
                        current_time,
                        booked_start_time,
                        total_service_duration,
                        staff_id,
                        interval_minutes,
                        appointment_date
                    )
                    time_slots.extend(slots)

                if booked_end_time > current_time:
                    current_time = booked_end_time

            if current_time < staff_working_end_time:
                slots = self._generate_time_slots(
                    current_time,
                    staff_working_end_time,
                    total_service_duration,
                    staff_id,
                    interval_minutes,
                    appointment_date
                )
                time_slots.extend(slots)

            return time_slots
        except Exception as e:
            raise Exception(f"Error checking staff availability: {e}")

    def get_all_available_time_slots(self, business_id, service_ids, appointment_date, service_duration):
        try:
            staffs = Staff.objects.filter(business=business_id, is_active=True)
            time_slots = []

            for staff in staffs:
                available_time_slots = self.get_staff_time_slots(
                    staff_id=staff.id,
                    service_ids=service_ids,
                    appointment_date=appointment_date,
                    service_duration=service_duration,
                )

                time_slots.extend(available_time_slots)

            # remove duplicate time slots by start_time
            unique_time_slots = []
            seen_time_slots = set()
            for slot in time_slots:
                slot_key = slot['start_time']
                if slot_key not in seen_time_slots:
                    unique_time_slots.append(slot)
                    seen_time_slots.add(slot_key)

            # sort unique_time_slots by start_time
            unique_time_slots.sort(key=lambda x: x['start_time'])

            return unique_time_slots
        except Exception as e:
            raise Exception(f"Error getting all available time slots: {e}")
        
    def _get_appointment_services_duration(self, appointment_services):
        try:
            total_duration = 0
            for appointment_service in appointment_services:
                total_duration += int(appointment_service['service_duration'])
            return total_duration
        except Exception as e:
            return 0
        
    def create_appointment_services(self, appointment, appointment_services):
        try:
            
            with transaction.atomic():
                
                total_duration = self._get_appointment_services_duration(appointment_services)
                
                client_minimum_booking_duration = self.get_client_minimum_booking_duration(
                    appointment['client_id'], 
                    total_duration
                )
                if client_minimum_booking_duration > total_duration:
                    appointment_services[0]['service_duration'] = client_minimum_booking_duration
                    if isinstance(appointment_services[0]['start_at'], str):
                        start_at_dt = parser.parse(appointment_services[0]['start_at'])
                    else:
                        start_at_dt = appointment_services[0]['start_at']
                    end_at_dt = start_at_dt + timedelta(minutes=client_minimum_booking_duration)
                    appointment_services[0]['end_at'] = end_at_dt
                
                created_appointment = Appointment.objects.create(
                    **appointment,                    
                )

                for appointment_service in appointment_services:
                    AppointmentService.objects.create(
                        id=appointment_service['id'],
                        appointment=created_appointment,
                        service_id=appointment_service['service'] or None,
                        staff_id=appointment_service['staff'],
                        is_staff_request=appointment_service['is_staff_request'],
                        start_at=appointment_service['start_at'],
                        end_at=appointment_service['end_at'],
                        custom_price=appointment_service['custom_price'],
                        custom_duration=appointment_service['service_duration'],
                    )
                    
                return created_appointment
        except Exception as e:
            raise Exception(f"Error creating appointment services: {e}")

    def find_my_upcoming_appointments(self, client_id) -> list[Appointment]:
        try:
            appointments = Appointment.objects.filter(
                client_id=client_id, 
                appointment_date__gte=timezone.now().date(),
                is_active=True,
                status=AppointmentStatusType.SCHEDULED.value,
                business_id=self.business_id
            ).order_by('appointment_date')
            
            return appointments
        except Exception as e:
            raise Exception(f"Error finding my appointments: {e}")
        
    def find_client_by_phone(self, phone) -> Client | None:
        try:
            client = Client.objects.filter(
                phone=phone, 
                is_active=True, 
                is_deleted=False,
                primary_business_id=self.business_id
            ).first()
            if not client:
                return None
            return client
        except Exception as e:
            raise Exception(f"Error finding client by phone: {e}")

    def cancel_appointment(self, appointment_id, client_id) -> Appointment | None:
        try:
            appointment = Appointment.objects.filter(
                id=appointment_id,
                client_id=client_id,
                is_active=True,
                status=AppointmentStatusType.SCHEDULED.value,
                business_id=self.business_id
            ).first()
            
            if not appointment:
                return None
            appointment.status = AppointmentStatusType.CANCELLED.value
            appointment.cancelled_at = timezone.now()
            appointment.save()
            return appointment
        except Exception as e:
            raise Exception(f"Error canceling appointment: {e}")
    
    def get_appointment(self, appointment_id) -> Appointment | None:
        try:
            appointment = Appointment.objects.get(
                id=appointment_id,
                is_active=True,
                business_id=self.business_id,
            )
            return appointment
        except Exception as e:
            raise Exception(f"Error getting appointment: {e}")
class BusinessStaffService:
    def __init__(self, business_id):
        self.business_id = business_id

    def get_business_active_technicians(self):
        try:
            return Staff.objects.filter(
                business_id=self.business_id,
                is_active=True,
                is_deleted=False,
                is_online_booking_allowed=True,
            )
        except Exception as e:
            raise Exception(f"Error getting business staffs: {e}")

class AppointmentBusinessService:
    def __init__(self, business_id):
        self.business_id = business_id

    def get_business_settings(self):
        try:
            return BusinessSettings.objects.get(business_id=self.business_id)
        except Exception as e:
            raise Exception(f"Error getting business settings: {e}")

class AppointmentNotificationService:
    def __init__(self, appointment):
        self.appointment = appointment
        self.dispatcher = NotificationDispatcher()

    def _build_services_context(self):
        """Build services list, total price, and total duration from appointment metadata."""
        services = []
        total_price = 0
        total_duration = 0
        metadata = self.appointment.metadata or {}
        appointment_services = metadata.get('appointment_services', [])
        for svc in appointment_services:
            price = svc.get('custom_price') or svc.get('service_price') or svc.get('price') or 0
            duration = svc.get('custom_duration') or svc.get('service_duration') or svc.get('duration_minutes') or 0
            services.append({
                'service_name': svc.get('service_name') or svc.get('name') or 'Service',
                'staff_name': svc.get('staff_name') or '',
                'price': price,
                'duration': duration,
            })
            total_price += float(price)
            total_duration += int(duration)
        return services, total_price, total_duration

    def send_client_confirmation_notification(
        self,
        client_name,
        client_phone,
        business_phone,
        business_name,
        appointment_id,
        start_at,
        metadata,
        business_twilio_phone_number,
        client_email=None,
        by_email=False,
        by_sms=False,
    ):
        try:
            business_id = self.appointment.business.id
            body_message = f"Your appointment #{appointment_id} has been confirmed at {start_at} at {business_name}. If you need to cancel or reschedule your appointment, please contact us at {business_phone}."

    
            if client_phone and by_sms:
                SMSService().send_async(
                    to_phone=client_phone,
                    body=body_message,
                    business_id=business_id,
                    business_twilio_phone_number=business_twilio_phone_number,
                )

            if client_email and by_email:
                services, total_price, total_duration = self._build_services_context()
                business = self.appointment.business
                EmailService().send_async(
                    subject=f"Appointment Confirmed - {business_name}",
                    to_email=client_email,
                    template="emails/appointment_confirmation.html",
                    context={
                        "client_name": client_name,
                        "business_name": business_name,
                        "appointment_id": appointment_id,
                        "start_at": start_at,
                        "business_phone": business_phone,
                        "business_address": business.address if business else '',
                        "services": services,
                        "total_price": total_price,
                        "total_duration": total_duration,
                    },
                )

        except Exception as e:
            logger.error(f"Error sending confirmation notification: {e}")
            raise Exception(f"Error sending confirmation notification: {e}")

    def send_client_reminder_notification(
        self,
        client_name,
        client_phone,
        business_phone,
        business_name,
        appointment_id,
        start_at,
        metadata,
        schedule_time,
        business_id,
        business_twilio_phone_number,
        business_timezone: str,
        client_email=None,
        by_sms=False,
        by_email=False,
    ):
        try:
            print("sending reminder notification to:: ", client_email)
            print("by_sms:: ", by_sms)
            print("by_email:: ", by_email)
            
            title = f"🔔 Appointment Reminder - {business_name}"
            body_message = f"Your appointment #{appointment_id} at {start_at} at {business_name} is coming up soon. If you need to cancel or reschedule your appointment, please contact us at {business_phone}."

            if client_phone and by_sms:
                reminder_schedule_name = get_reminder_schedule_name(
                    business_id, 
                    appointment_id, 
                    channel='sms'
                )
                SMSService().send_scheduled(
                    to_phone=client_phone,
                    body=body_message,
                    business_id=business_id,
                    schedule_name=reminder_schedule_name,
                    schedule_time=schedule_time,
                    business_twilio_phone_number=business_twilio_phone_number,
                    schedule_expression_timezone=business_timezone,
                )

            if client_email and by_email:
                reminder_schedule_name = get_reminder_schedule_name(
                    business_id,
                    appointment_id,
                    channel='email'
                )
                services, total_price, total_duration = self._build_services_context()
                business = self.appointment.business
                EmailService().send_scheduled(
                    subject=f"Appointment Reminder - {business_name}",
                    to_email=client_email,
                    template="emails/appointment_reminder.html",
                    context={
                        "client_name": client_name,
                        "business_name": business_name,
                        "appointment_id": appointment_id,
                        "start_at": start_at,
                        "business_phone": business_phone,
                        "business_address": business.address if business else '',
                        "services": services,
                        "total_price": total_price,
                        "total_duration": total_duration,
                    },
                    schedule_name=reminder_schedule_name,
                    schedule_time=schedule_time,
                    schedule_expression_timezone=business_timezone,
                )

        except Exception as e:
            logger.error(f"Error sending reminder notification: {e}")
            raise Exception(f"Error sending reminder notification: {e}")

    def send_client_rescheduled_notification(
        self,
        client_name,
        client_phone,
        business_phone,
        business_name,
        appointment_id,
        business_id,
        start_at_str,
        metadata,
        business_twilio_phone_number,
        client_email=None,
        by_sms=False,
        by_email=False,
    ):
        try:
            body_message = f"Your appointment #{appointment_id} has been rescheduled to {start_at_str} at {business_name}. If you need to cancel or reschedule your appointment, please contact us at {business_phone}."

            if client_phone and by_sms:
                SMSService().send_async(
                    to_phone=client_phone,
                    body=body_message,
                    business_id=business_id,
                    business_twilio_phone_number=business_twilio_phone_number,
                )
                reminder_schedule_name = get_reminder_schedule_name(
                    business_id, 
                    appointment_id, 
                    channel='sms'
                )
                SMSService().destroy_scheduled(schedule_name=reminder_schedule_name)

            if client_email and by_email:
                services, total_price, total_duration = self._build_services_context()
                business = self.appointment.business
                EmailService().send_async(
                    subject=f"Appointment Rescheduled - {business_name}",
                    to_email=client_email,
                    template="emails/appointment_rescheduled.html",
                    context={
                        "client_name": client_name,
                        "business_name": business_name,
                        "appointment_id": appointment_id,
                        "start_at": start_at_str,
                        "business_phone": business_phone,
                        "business_address": business.address if business else '',
                        "services": services,
                        "total_price": total_price,
                        "total_duration": total_duration,
                    },
                )

        except Exception as e:
            logger.error(f"Error sending rescheduled notification: {e}")
            raise Exception(f"Error sending rescheduled notification: {e}")
    
    def send_client_cancellation_notification(
        self,
        client_name,
        client_phone,
        business_phone,
        business_name,
        appointment_id,
        business_id,
        start_at_str,
        metadata,
        business_twilio_phone_number,
        client_email=None,
        by_sms=False,
        by_email=False,
    ):
        try:
            body_message = f"Your appointment #{appointment_id} at {start_at_str} at {business_name} has been cancelled. Please contact us at {business_phone} if you have any questions."

            if client_phone and by_sms:
                SMSService().send_async(
                    to_phone=client_phone,
                    body=body_message,
                    business_id=business_id,
                    business_twilio_phone_number=business_twilio_phone_number,
                )
            reminder_schedule_name = get_reminder_schedule_name(
                    business_id, 
                    appointment_id, 
                    channel='sms'
                )
            if reminder_schedule_name:
                SMSService().destroy_scheduled(schedule_name=reminder_schedule_name)

            if client_email and by_email:
                services, total_price, total_duration = self._build_services_context()
                business = self.appointment.business
                EmailService().send_async(
                    subject=f"Appointment Cancelled - {business_name}",
                    to_email=client_email,
                    template="emails/appointment_cancelled.html",
                    context={
                        "client_name": client_name,
                        "business_name": business_name,
                        "appointment_id": appointment_id,
                        "start_at": start_at_str,
                        "business_phone": business_phone,
                        "business_address": business.address if business else '',
                        "services": services,
                        "total_price": total_price,
                        "total_duration": total_duration,
                    },
                )

            reminder_schedule_name = get_reminder_schedule_name(
                    business_id, 
                    appointment_id, 
                    channel='email'
                )
            if reminder_schedule_name:
                EmailService().destroy_scheduled(schedule_name=reminder_schedule_name)
                
        except Exception as e:
            logger.error(f"Error sending cancellation notification: {e}")
            raise Exception(f"Error sending cancellation notification: {e}")
    
    # staff notifications
    def send_staff_appointment_confirmation_notification(
        self,
        staff,
        title,
        body_message,
        metadata,
    ):  
        try:
            
            self.dispatcher.dispatchAsync(
                title=title,
                body=body_message,
                data=metadata,
                channel=Notification.Channel.PUSH,
                to=staff,
            )
        except Exception as e:
            logger.error(f"Error sending appointment confirmation Push: {e}")
            raise Exception(f"Error sending appointment confirmation Push: {e}")
        

    def send_manager_appointment_confirmation_notification(
        self,
        title,
        body_message,
        metadata,
        business_id,
    ):
        try:
            self.dispatcher.dispatchAsync(
                title=title,
                body=body_message,
                data=metadata,
                business_id=business_id,
                channel=Notification.Channel.PUSH,
                group_name=get_business_managers_group_name(business_id),
                to=None,
            )
        except Exception as e:
            raise Exception(f"Error sending manager appointment confirmation Push: {e}")
        
    def send_staff_and_manager_payment_notification(
        self,
        title,
        body_message,
        metadata,
        staff,
        business_id,
    ):
        try:
            self.dispatcher.dispatchAsync(
                title=title,
                body=body_message,
                data=metadata,
                channel=Notification.Channel.PUSH,
                to=staff,
            )
            
            self.dispatcher.dispatchAsync(
                title=title,
                body=body_message,
                data=metadata,
                channel=Notification.Channel.PUSH,
                group_name=get_business_managers_group_name(business_id),
                to=None,
            )
        except Exception as e:
            logger.error(f"Error sending staff payment notification: {e}")
            raise Exception(f"Error sending staff payment notification: {e}")
    
    @staticmethod
    def send_client_review_request(appointment: Appointment):
        try:
            metadata = appointment.metadata or {}
            business = appointment.business
            review_url = f"{ONLINE_BOOKING_URL}/review/?appointment_id={appointment.id}&business_id={business.id}"
            body_message = f"🤗 Thank you for choosing us. Please leave a review to help us improve our services at {review_url} and contact us at {business.phone_number} if you have any questions."
            
            title = f"Leave a Review - {business.name}"
            schedule_name = f"leave-review-sms3-{business.id}-{appointment.id}"
            schedule_time = timezone.now() + timedelta(seconds=10)
            bs = BusinessSettings.objects.filter(business_id=business.id).first()
            review_tz = bs.timezone if bs else None

            NotificationDispatcher().dispatch_scheduled(
                title=title,
                body=body_message,
                data=metadata,
                channel=Notification.Channel.SMS,
                to=appointment.client.phone,
                business_id=business.id,
                business_twilio_phone_number=business.twilio_phone_number,
                schedule_name=schedule_name,
                schedule_time=schedule_time,
                schedule_expression_timezone=review_tz,
            )
        except Exception as e:
            raise Exception(f"Error sending review request Push: {e}")
    
    @staticmethod
    def send_manager_cancellation_appointment_notification(
        client_name: str, 
        start_time_str: str,
        business_name: str,
        business_id: int,
    ):
        try:
            body_message = f"{client_name} has cancelled their appointment at {start_time_str} at {business_name}."
            title = f"❌ Appointment Cancelled - {business_name}"
            
            NotificationDispatcher().dispatchAsync(
                title=title,
                body=body_message,
                business_id=business_id,
                channel=Notification.Channel.PUSH,
                group_name=get_business_managers_group_name(business_id),
                to=None,
            )
        except Exception as e:
            raise Exception(f"Error sending cancellation appointment notification: {e}")

    @staticmethod
    def send_manager_rescheduled_appointment_notification(
        business_name: str,
        business_id: int,
        client_name: str,
        start_time_str: str,
    ):
        try:
            body_message = f"Client {client_name} has rescheduled their appointment to {start_time_str} at {business_name}."
            title = f"🔔 Appointment Rescheduled - {business_name}"
            NotificationDispatcher().dispatchAsync(
                title=title,
                body=body_message,
                business_id=business_id,
                channel=Notification.Channel.PUSH,
                group_name=get_business_managers_group_name(business_id),
                to=None,
            )
        except Exception as e:
            raise Exception(f"Error sending manager rescheduled appointment notification: {e}")

class TicketReportService():
    def __init__(self, business_id):
        self.business_id = business_id
    
    def get_ticket_report_summary(self, from_date, to_date, staff_id=None):
        try:
            queryset = AppointmentService.objects.filter(
                appointment__business_id=self.business_id,
                appointment__appointment_date__gte=from_date,
                appointment__appointment_date__lte=to_date,
                appointment__status=AppointmentStatusType.CHECKED_OUT.value,
                is_active=True,
                is_deleted=False,
            )
            
            if staff_id:
                queryset = queryset.filter(staff_id=staff_id)
                
            staff_sales = queryset.values('staff').annotate(
                staff_first_name=F('staff__first_name'),
                staff_last_name=F('staff__last_name'),
                commission_rate=F('staff__commission_rate'),
                total_service_sales=Sum('custom_price'),
                total_service_tips=Sum('tip_amount'),
                total_services=Count('id'),
                from_date=Value(from_date, output_field=DateField()),
                to_date=Value(to_date, output_field=DateField()),
            )
            
            # order by total_service_sales descending
            staff_sales = staff_sales.order_by('-total_service_sales')
            
            # payment ticket report
            payment_queryset = Payment.objects.filter(
                appointment__business_id=self.business_id,
                appointment__appointment_date__gte=from_date,
                appointment__appointment_date__lte=to_date,
                status=PaymentStatusType.COMPLETED.value,
            )
            
            payment_statistics = payment_queryset.aggregate(
                total_sales=Sum('amount'),
                cash_method_sales=Sum('amount', filter=Q(payment_method__name='Cash')),
                card_method_sales=Sum('amount', filter=Q(payment_method__name='Credit Card')),
                debit_card_method_sales=Sum('amount', filter=Q(payment_method__name='Debit Card')),
                bank_transfer_method_sales=Sum('amount', filter=Q(payment_method__name='Bank Transfer')),
                cheque_method_sales=Sum('amount', filter=Q(payment_method__name='Cheque')),
                gift_card_method_sales=Sum('amount', filter=Q(payment_method__name='Gift Card')),
                online_method_sales=Sum('amount', filter=Q(payment_method__name='Online')),
                other_method_sales=Sum('amount', filter=Q(payment_method__name='Other')),
            )
            
            summary = queryset.aggregate(
                total_sales=Sum('custom_price'),
                total_tips=Sum('tip_amount'),
                total_services=Count('id'),
            )
            summary['from_date'] = from_date
            summary['to_date'] = to_date
            summary['total_staffs'] = staff_sales.count()
            summary['payment_stats'] = payment_statistics
            
            return {
                'summary': summary,
                'data': staff_sales,
            }
        except Exception as e:
            raise Exception(f"Error getting ticket report: {e}")
        
    def get_staff_ticket_report_summary(self, from_date, to_date, staff_id):
        try:
            queryset = AppointmentService.objects.filter(
                appointment__business_id=self.business_id,
                appointment__appointment_date__gte=from_date,
                appointment__appointment_date__lte=to_date,
                appointment__status=AppointmentStatusType.CHECKED_OUT.value,
                is_active=True,
                is_deleted=False,
            )
            
            if staff_id:
                queryset = queryset.filter(staff_id=staff_id)
                
            staff_sales = queryset.values('staff').annotate(
                staff_first_name=F('staff__first_name'),
                staff_last_name=F('staff__last_name'),
                commission_rate=F('staff__commission_rate'),
                total_service_sales=Sum('custom_price'),
                total_service_tips=Sum('tip_amount'),
                total_services=Count('id'),
                from_date=Value(from_date, output_field=DateField()),
                to_date=Value(to_date, output_field=DateField()),
            )
            
            # order by total_service_sales descending
            staff_sales = staff_sales.order_by('-total_service_sales')
            
            summary = queryset.aggregate(
                total_sales=Sum('custom_price'),
                total_tips=Sum('tip_amount'),
                total_services=Count('id'),
            )
            summary['from_date'] = from_date
            summary['to_date'] = to_date
            summary['total_staffs'] = staff_sales.count()
            
            return {
                'summary': summary,
                'data': staff_sales,
            }
        except Exception as e:
            raise Exception(f"Error getting staff ticket report summary: {e}")
        
    def get_ticket_report_by_dates(self, from_date, to_date, staff_id):
        try:
            queryset = AppointmentService.objects.filter(
                appointment__business_id=self.business_id,
                appointment__appointment_date__gte=from_date,
                appointment__appointment_date__lte=to_date,
                appointment__status=AppointmentStatusType.CHECKED_OUT.value,
                staff_id=staff_id,
                is_active=True,
                is_deleted=False,
            )
            
            queryset = queryset.order_by('-appointment__appointment_date')
            staff_sales = queryset.values('appointment__appointment_date').annotate(
                staff_first_name=F('staff__first_name'),
                staff_last_name=F('staff__last_name'),
                commission_rate=F('staff__commission_rate'),
                staff=F('staff__id'),
                total_service_sales=Sum('custom_price'),
                total_service_tips=Sum('tip_amount'),
                total_services=Count('id'),
                appointment_date=F('appointment__appointment_date'),
            )
            total_tips = queryset.aggregate(total_tips=Sum('tip_amount'))['total_tips'] or 0
            total_tips_by_cash = queryset.filter(tip_method=PaymentMethodType.CASH.value).aggregate(total_tips=Sum('tip_amount'))['total_tips'] or 0
            total_tips_by_card = total_tips - total_tips_by_cash
            
            summary = queryset.aggregate(
                total_sales=Sum('custom_price'),
                total_tips=Sum('tip_amount'),
                total_services=Count('id'),
            )
            summary['total_cash_tips'] = total_tips_by_cash
            summary['total_card_tips'] = total_tips_by_card
            summary['from_date'] = from_date
            summary['to_date'] = to_date
                
            return {
                'summary': summary,
                'data': staff_sales,
            }
        except Exception as e:
            raise Exception(f"Error getting staff ticket report summary: {e}")
        
    def get_ticket_report_by_date(self, staff_id, date) -> dict:
        try:
            queryset = AppointmentService.objects.filter(
                appointment__business_id=self.business_id,
                appointment__appointment_date=date,
                appointment__status=AppointmentStatusType.CHECKED_OUT.value,
                staff_id=staff_id,
                is_active=True,
                is_deleted=False,
            )
            
            queryset = queryset.order_by('-updated_at')
            staff_sales = queryset.values('appointment__appointment_date').annotate(
                staff_first_name=F('staff__first_name'),
                staff_last_name=F('staff__last_name'),
                commission_rate=F('staff__commission_rate'),
                staff=F('staff__id'),
                appointment_id=F('appointment__id'),
                service_id=F('service__id'),
                service_name=F('service__name'),
                service_duration=F('service__duration_minutes'),
                custom_price=F('custom_price'),
                tip_amount=F('tip_amount'),
                tip_method=F('tip_method'),
                client_name=F('appointment__client__first_name'),
                updated_at=F('appointment__updated_at'),
                created_at=F('appointment__created_at'),
            )
            
            # total tips
            total_tips = queryset.aggregate(total_tips=Sum('tip_amount'))['total_tips'] or 0
            total_cash_tips = queryset.filter(tip_method=PaymentMethodType.CASH.value).aggregate(total_tips=Sum('tip_amount'))['total_tips'] or 0
            total_card_tips = total_tips - total_cash_tips
            
            summary = queryset.aggregate(
                total_sales=Sum('custom_price'),
                total_tips=Sum('tip_amount'),
                total_services=Count('id'),
            )
            summary['total_cash_tips'] = total_cash_tips
            summary['total_card_tips'] = total_card_tips
            
            return {
                'summary': summary,
                'data': staff_sales,
            }
        except Exception as e:
            raise Exception(f"Error getting ticket report by date: {e}")

class SalaryReportService:
    """Service for generating salary reports with commission calculations"""
    
    def __init__(self, business_id):
        self.business_id = business_id
        self.ticket_report_service = TicketReportService(business_id)
    

    def _calculate_commission(self, sales_amount: float, commission_rate: float) -> float:
        """Calculate commission amount from sales and commission rate"""
        if sales_amount is None or commission_rate is None:
            return 0
        commission_amount = float(sales_amount) * float(commission_rate)
        return commission_amount
    
    def _enrich_data_with_commission(self, data: list) -> tuple[list, float]:
        enriched_data = []
        total_commission = 0
        for item in data:
            sales = item['total_service_sales'] or 0
            commission_rate = item['commission_rate'] or 0
            commission_amount = self._calculate_commission(sales, commission_rate)
            item['commission_amount'] = commission_amount
            total_commission += commission_amount
            enriched_data.append(item)
        return enriched_data, total_commission
    
    def get_salary_report_summary(self, from_date, to_date, staff_id=None):
        """
        Get salary report summary with commission calculations
        
        Args:
            from_date: Start date for report
            to_date: End date for report
            staff_id: Optional staff ID to filter by specific staff
            
        Returns:
            Dict with summary and per-staff data including commission
        """
        try:
            # Get ticket report data
            ticket_data = self.ticket_report_service.get_ticket_report_summary(
                from_date, to_date, staff_id
            )
            
            summary = ticket_data['summary']
            enriched_data = ticket_data['data']
            
            # Enrich data with commission calculations
            enriched_data, total_commission = self._enrich_data_with_commission(enriched_data)
            summary['total_commission'] = total_commission
            
            # Calculate total revenue
            total_sales = summary['total_sales'] or 0
            total_revenue = float(total_sales) - float(total_commission)
            summary['total_revenue'] = total_revenue
            
            return {
                'summary': summary,
                'data': enriched_data,
            }
        except Exception as e:
            raise Exception(f"Error getting salary report summary: {e}")
    
    def get_salary_report_by_dates(self, from_date, to_date, staff_id):
        """
        Get salary report by dates (daily breakdown) with commission calculations
        
        Args:
            from_date: Start date for report
            to_date: End date for report
            staff_id: Staff ID (required)
            
        Returns:
            Dict with summary and daily breakdown including commission
        """
        try:
            # Get ticket report data by dates
            ticket_data = self.ticket_report_service.get_ticket_report_by_dates(
                from_date, to_date, staff_id
            )
            
            # Enrich data with commission calculations
            enriched_data = []
            total_commission = 0
            commission_rate = 0
            for item in ticket_data['data']:
                sales = item['total_service_sales'] or 0
                commission_rate = item['commission_rate'] or 0
                commission_amount = self._calculate_commission(sales, commission_rate)
                
                if commission_amount is not None:
                    total_commission += commission_amount
                
                enriched_data.append({
                    'staff': item['staff'],
                    'staff_first_name': item['staff_first_name'],
                    'staff_last_name': item['staff_last_name'],
                    'appointment_date': item['appointment_date'],
                    'total_service_sales': sales,
                    'commission_rate': commission_rate,
                    'commission_amount': commission_amount,
                    'total_services': item['total_services'],
                })
            
            # Build summary with commission
            summary = ticket_data['summary'].copy()
            summary['total_commission'] = total_commission
            
            return {
                'summary': summary,
                'data': enriched_data,
            }
        except Exception as e:
            raise Exception(f"Error getting salary report by dates: {e}")
    
    def get_salary_report_by_date(self, staff_id, date):
        """
        Get detailed salary report for a specific staff on a specific date
        
        Args:
            staff_id: Staff ID (required)
            date: Specific date for report
            
        Returns:
            Dict with summary and detailed service breakdown including commission
        """
        try:
            # Get ticket report data by date
            ticket_data = self.ticket_report_service.get_ticket_report_by_date(
                staff_id, date
            )
            
            # Get commission rate from the first item in data (all items have same staff)
            commission_rate = 0
            if ticket_data['data']:
                # Commission rate is included in the ticket data
                first_item = list(ticket_data['data'])[0]
                commission_rate = first_item.get('commission_rate', 0)
            else:
                # If no data, get commission rate directly from Staff model
                try:
                    staff = Staff.objects.get(id=staff_id, is_active=True)
                    commission_rate = staff.commission_rate or 0
                except Staff.DoesNotExist:
                    commission_rate = 0
            
            # Calculate total commission for the day
            total_sales = ticket_data['summary']['total_sales'] or 0
            total_commission = self._calculate_commission(total_sales, commission_rate)
            
            # Enrich each service record with commission
            enriched_data = []
            for item in ticket_data['data']:
                service_price = item.get('custom_price') or 0
                service_commission = self._calculate_commission(service_price, commission_rate)
                
                enriched_data.append({
                    'staff': item['staff'],
                    'staff_first_name': item['staff_first_name'],
                    'staff_last_name': item['staff_last_name'],
                    'appointment_id': item.get('appointment_id'),
                    'service_id': item.get('service_id'),
                    'service_name': item.get('service_name'),
                    'service_duration': item.get('service_duration'),
                    'custom_price': service_price,
                    'commission_rate': commission_rate,
                    'commission_amount': service_commission,
                    'tip_amount': item.get('tip_amount'),
                    'tip_method': item.get('tip_method'),
                    'client_name': item.get('client_name'),
                    'updated_at': item.get('updated_at'),
                    'created_at': item.get('created_at'),
                })
            
            # Build summary with commission
            summary = ticket_data['summary'].copy()
            summary['total_commission'] = total_commission
            summary['commission_rate'] = commission_rate
            
            return {
                'summary': summary,
                'data': enriched_data,
            }
        except Exception as e:
            raise Exception(f"Error getting salary report by date: {e}")
        

class CalendarStaffService:
    def __init__(self, business_id, auth_user, weekday, appointment_date):
        self.business_id = business_id
        self.auth_user = auth_user
        self.weekday = weekday
        self.appointment_date = appointment_date
    
    def _get_business_staffs(self) -> QuerySet[Staff]:
        try:
            if self.auth_user.role.name in ['Manager', 'Owner', 'Receptionist']:
                
                override_staffs = self._get_business_staffs_overrides()
                
                business_staffs = Staff.objects.filter(
                    business_id=self.business_id,
                    is_active=True,
                    is_online_booking_allowed=True,
                    working_hours__is_working=True,
                    working_hours__day_of_week=self.weekday,
                    role__name__in=['Technician', 'Stylist'],
                )
                
                if override_staffs.exists():
                    # add staff working hours overrides to business staffs
                    business_staffs = (business_staffs | override_staffs).distinct()
            else:
                business_staffs = Staff.objects.filter(
                    id=self.auth_user.id,
                )
            
            return business_staffs
        
        except Exception as e:
            raise Exception(f"Error getting business staffs: {e}")
    
    def _get_business_staffs_overrides(self) -> QuerySet[Staff]:
        try:
            override_staffs = StaffWorkingHoursOverride.objects.filter(
                staff__business_id=self.business_id,
                date=self.appointment_date,
                is_working=True,
            )
            staffs = override_staffs.values_list('staff__id', flat=True)
            
            override_staffs = Staff.objects.filter(
                id__in=staffs,
                is_active=True,
                is_online_booking_allowed=True,
                role__name__in=['Technician', 'Stylist'],
            ).all()
            
            return override_staffs
        except Exception as e:
            raise Exception(f"Error getting business staffs overrides: {e}")
        
    def _get_staff_off_days(self, business_staffs) -> QuerySet[StaffOffDay]:
        try:
            staff_off_days = StaffOffDay.objects.filter(
                staff__id__in=business_staffs.values_list('id', flat=True),
                start_date__lte=self.appointment_date,
                end_date__gte=self.appointment_date,
            )
            return staff_off_days
        except Exception as e:
            raise Exception(f"Error getting staff off days: {e}")
        
    def _handle_staff_on_leave(
        self,
        staff_off_days: QuerySet[StaffOffDay],
        business_staffs: QuerySet[Staff],
    ) -> QuerySet[Staff]:
        try:
            staff_on_leave_ids = set(
                staff_off_days.values_list('staff__id', flat=True)
            )
            staff_off_day_appointments = AppointmentService.objects.filter(
                staff_id__in=staff_on_leave_ids,
                appointment__appointment_date=self.appointment_date,
            )
            staff_on_leave_with_appointments = set(
                staff_off_day_appointments.values_list('staff_id', flat=True)
            )
            staff_on_leave_without_appointments = (
                staff_on_leave_ids - staff_on_leave_with_appointments
            )
            available_staffs = business_staffs.exclude(
                id__in=staff_on_leave_without_appointments
            )
            return available_staffs

        except Exception as e:
            raise Exception(f"Error getting staff on leave with appointments: {e}")
    
    def get_calendar_staffs(self) -> QuerySet[Staff]:
        try:
            # Get staff with role and who are working on the appointment date
            business_staffs = self._get_business_staffs()
            
            # Get staff who have an off day on the appointment date
            staff_off_days = self._get_staff_off_days(business_staffs)
            
            # Get staff who are available for the appointment date
            if staff_off_days.exists():
                return self._handle_staff_on_leave(staff_off_days, business_staffs)
            else:
                return business_staffs
        
        except Exception as e:
            raise Exception(f"Error getting calendar staffs: {e}")

    def get_all_technicians(self) -> QuerySet[Staff]:
        try:
            if self.auth_user.role.name in ['Manager', 'Owner', 'Receptionist']:
                technicians = Staff.objects.filter(
                    business_id=self.business_id,
                    is_active=True,
                    is_online_booking_allowed=True,
                    role__name__in=['Technician', 'Stylist'],
                )
                return technicians
            else:
                return Staff.objects.filter(
                    id=self.auth_user.id,
                    role__name__in=['Technician', 'Stylist'],
                )
        except Exception as e:
            raise Exception(f"Error getting all technicians: {e}")