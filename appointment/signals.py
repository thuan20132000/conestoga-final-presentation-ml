import logging
from re import S
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction

from appointment.serializers import AppointmentServiceSerializer, AppointmentSerializer
from business.models import BusinessSettings
from .models import Appointment, AppointmentService, AppointmentStatusType
from notifications.models import Notification
from notifications.services import NotificationDispatcher, NotificationService
from datetime import datetime, timedelta
from appointment.services import AppointmentNotificationService
import time
from django.contrib.auth.models import User
from staff.models import Staff

logger = logging.getLogger(__name__)
dispatcher = NotificationDispatcher()


@receiver(post_save, sender=Appointment)
def handle_appointment_notifications(sender, instance, created, **kwargs):
    """Handle notifications for appointment creation and updates"""

    try:
        if instance.is_active == False:
            return

        appointment_data = AppointmentSerializer(instance).data
        client_name = appointment_data.get('client_name', 'A client')
        client_phone = appointment_data.get('client_phone', None)
        business_phone = appointment_data.get(
            'business_phone_number', 'Unknown')
        business_name = appointment_data.get(
            'business_name', 'A business')
        business_twilio_phone_number = appointment_data.get(
            'business_twilio_phone_number', None)

        client_email = appointment_data.get('client_email', None)
        appointment_id = appointment_data.get('id', None)
        business_id = appointment_data.get('business', None)

        # get business settings
        business_settings = BusinessSettings.objects.get(
            business_id=business_id
        )
        send_confirmation_sms = business_settings.send_confirmation_sms if business_settings else False
        send_confirmation_email = business_settings.send_confirmation_email if business_settings else False
        send_reminder_email = business_settings.send_reminder_emails if business_settings else False
        send_reminder_sms = business_settings.send_reminder_sms if business_settings else False
        send_cancellation_sms = business_settings.send_cancellation_sms if business_settings else False
        send_cancellation_email = business_settings.send_cancellation_email if business_settings else False

        business_timezone = business_settings.timezone

        timezone.activate(business_timezone)

        reminder_hours_before = business_settings.reminder_hours_before if business_settings else 2
        start_at = appointment_data.get('start_at')
        start_at_obj = datetime.fromisoformat(start_at)
        start_at_str = start_at_obj.strftime("%I:%M %p on %B %d, %Y")
        payment_status = appointment_data.get('payment_status', None)

        metadata = instance.metadata
        schedule_time = start_at_obj - timedelta(
            hours=reminder_hours_before,
            minutes=0,
        )
        appointment_status = appointment_data.get('status', None)

        appointment_notification_service = AppointmentNotificationService(
            instance)

        if not client_phone and not client_email:
            return

        with transaction.atomic():
            if created:
                # check if confirmation sms and email is enabled
                is_send_confirmation_sms = send_confirmation_sms and metadata.get(
                    'is_send_confirmation_sms', False)
                is_send_confirmation_email = send_confirmation_email and metadata.get(
                    'is_send_confirmation_email', True)

                appointment_notification_service.send_client_confirmation_notification(
                    client_name=client_name,
                    client_phone=client_phone,
                    business_phone=business_phone,
                    business_name=business_name,
                    appointment_id=appointment_id,
                    start_at=start_at_str,
                    metadata=metadata,
                    business_twilio_phone_number=business_twilio_phone_number,
                    client_email=client_email,
                    by_sms=is_send_confirmation_sms,
                    by_email=is_send_confirmation_email,
                )

                # check if reminder email and sms is enabled
                is_send_reminder_email = send_reminder_email and metadata.get(
                    'is_send_reminder_email', True)
                is_send_reminder_sms = send_reminder_sms and metadata.get(
                    'is_send_reminder_sms', False)
              
                if schedule_time > timezone.now():
                    appointment_notification_service.send_client_reminder_notification(
                        client_name=client_name,
                        client_phone=client_phone,
                        business_phone=business_phone,
                        business_name=business_name,
                        appointment_id=appointment_id,
                        business_id=business_id,
                        start_at=start_at_str,
                        metadata=metadata,
                        schedule_time=schedule_time,
                        business_twilio_phone_number=business_twilio_phone_number,
                        business_timezone=business_timezone,
                        client_email=client_email,
                        by_sms=is_send_reminder_sms,
                        by_email=is_send_reminder_email,
                    )
                
            else:
                # Appointment rescheduled
                is_send_sms_rescheduled_confirmation = metadata.get(
                    'is_send_sms_rescheduled_confirmation', False)
                is_send_email_rescheduled_confirmation = metadata.get(
                    'is_send_email_rescheduled_confirmation', False)
                
                if is_send_sms_rescheduled_confirmation or is_send_email_rescheduled_confirmation:
                    appointment_notification_service.send_client_rescheduled_notification(
                        client_name=client_name,
                        client_phone=client_phone,
                        business_phone=business_phone,
                        business_name=business_name,
                        appointment_id=appointment_id,
                        business_id=business_id,
                        start_at_str=start_at_str,
                        metadata=metadata,
                        business_twilio_phone_number=business_twilio_phone_number,
                        client_email=client_email,
                        by_sms=is_send_sms_rescheduled_confirmation,
                        by_email=is_send_email_rescheduled_confirmation,
                    )

                if appointment_status == AppointmentStatusType.CANCELLED.value:
                    is_send_sms_cancellation_confirmation = send_cancellation_sms and metadata.get(
                        'is_send_sms_cancellation_confirmation', False)
                    is_send_email_cancellation_confirmation = send_cancellation_email and metadata.get(
                        'is_send_email_cancellation_confirmation', False)

                    appointment_notification_service.send_manager_cancellation_appointment_notification(
                        business_name=business_name,
                        business_id=business_id,
                        client_name=client_name,
                        start_time_str=start_at_str,
                    )
                    
                    appointment_notification_service.send_client_cancellation_notification(
                        client_name=client_name,
                        client_phone=client_phone,
                        business_phone=business_phone,
                        business_name=business_name,
                        appointment_id=appointment_id,
                        business_id=business_id,
                        start_at_str=start_at_str,
                        metadata=metadata,
                        business_twilio_phone_number=business_twilio_phone_number,
                        client_email=client_email,
                        by_sms=is_send_sms_cancellation_confirmation,
                        by_email=is_send_email_cancellation_confirmation,
                    )

                # send push notification to business managers when appointment is rescheduled
                if metadata.get('is_rescheduled', False) == True:
                    appointment_notification_service.send_manager_rescheduled_appointment_notification(
                        business_name=business_name,
                        business_id=business_id,
                        client_name=client_name,
                        start_time_str=start_at_str,
                    )
                    

    except Exception as e:
        # logger.error(f"Error handling appointment notifications: {e}")
        print("Error handling appointment notifications", e)
        return
    finally:
        timezone.deactivate()


@receiver(post_save, sender=AppointmentService)
def handle_appointment_service_added(sender, instance, created, **kwargs):
    """Handle notifications for appointment service changes"""

    metadata = instance.metadata

    # POS payment notifications
    if metadata and metadata.get('is_pos_payment', False) == True:
        return

    appointment = AppointmentSerializer(instance.appointment).data
    booking_source = appointment.get('booking_source', '')
    appointment_service = AppointmentServiceSerializer(instance).data
    client_name = appointment_service.get('client_name', 'A client')
    service_name = appointment_service.get(
        'service_name', 'Unknown Service')
    business_name = appointment.get('business_name', 'Unknown Business')
    business_id = appointment.get('business', None)
    staff_name = appointment_service.get('staff_name', 'Unknown Staff')

    staff_id = appointment_service.get('staff', None)
    start_time_obj = datetime.fromisoformat(
        appointment_service.get('start_at'))
    start_time_str = start_time_obj.strftime("%I:%M %p on %B %d, %Y")
    is_staff_request = appointment_service.get('is_staff_request')
    booking_source = f"({booking_source})" if booking_source else ""
    staff_obj = Staff.objects.get(id=staff_id)

    appointment_notification_service = AppointmentNotificationService(instance)

    if created:

        staff_name = f"❤️ {staff_name}" if is_staff_request else "Anyone"

        title = f"🔔 Appointment - {business_name}"
        body_message = f"{booking_source} {client_name} booked {service_name} appointment at {start_time_str} with {staff_name}"

        # Staff appointment confirmation notifications
        appointment_notification_service.send_staff_appointment_confirmation_notification(
            title=title,
            staff=staff_obj,
            body_message=body_message,
            metadata=metadata,
        )
        appointment_notification_service.send_manager_appointment_confirmation_notification(
            title=title,
            body_message=body_message,
            metadata=metadata,
            business_id=business_id,
        )