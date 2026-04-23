from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from payment.serializers import PaymentDetailSerializer, PaymentSerializer
from payment.models import Payment
from payment.services import PaymentService
from appointment.models import Appointment
from main.utils import get_business_managers_group_name
from staff.models import Staff
from notifications.models import Notification
from notifications.services import NotificationDispatcher, NotificationService


dispatcher = NotificationDispatcher()

@receiver(post_save, sender=Payment)
def handle_payment_notifications(sender, instance, created, **kwargs):
    """Handle notifications for payment creation and updates"""
    try:
        payment_data = PaymentDetailSerializer(instance).data
        payment_status = payment_data.get('status', None)
        business_name = payment_data.get('business_name', None)
        business_id = payment_data.get('business', None)
        appointment = payment_data.get('appointment', None)
        appointment_services = appointment.get('appointment_services', None)

        if appointment_services and len(appointment_services) > 0:
            # Send notifications for appointment services
            payment_method_name = payment_data.get('payment_method_name', None)
            total_amount = payment_data.get('amount', 0)
            title = f"🧾 {payment_status.capitalize()}"
            body = ""
            
            for appointment_service in appointment_services:
                staff_name = appointment_service.get('staff_name', '')
                custom_price = appointment_service.get('custom_price', 0)
                tip_amount = appointment_service.get('tip_amount', 0)
                body += f"{staff_name} - ${custom_price} - Tip: ${tip_amount};\n"
            
            body += f"Paid ({payment_method_name}): ${total_amount}"
            
            # Send notifications to business managers
            dispatcher.dispatchAsync(
                title=title,
                body=body,
                data=payment_data,
                channel=Notification.Channel.PUSH,
                to=None,
                group_name=get_business_managers_group_name(business_id),
                business_id=business_id,
            )
            
            # Send notifications to staff
            for appointment_service in appointment_services:
                staff = Staff.objects.get(id=appointment_service.get('staff', None))
                dispatcher.dispatchAsync(
                    title=title,
                    body=body,
                    data=payment_data,
                    channel=Notification.Channel.PUSH,
                    to=staff,
                    business_id=business_id,
                )
                
            
       
    except Exception as e:
        print("error handling payment notifications:: ", e)
        return
    finally:
        print("payment notifications handled:: ", instance)
        return