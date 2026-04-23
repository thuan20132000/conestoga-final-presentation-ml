from notifications.models import Notification
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone as django_timezone
from main import common_settings
import boto3
import json
from pathlib import Path

# from pywebpush import webpush
from webpush import send_group_notification, send_user_notification
import asyncio
import time
from django.contrib.auth.models import User
import threading
from staff.models import Staff

logger = logging.getLogger(__name__)


def json_safe_metadata(metadata: Optional[Dict]) -> Optional[Dict]:
    """
    Recursively convert values to JSON-serializable types for JSONField.
    Handles UUID, Decimal, datetime, etc. via round-trip with default=str.
    """
    if metadata is None:
        return None
    return json.loads(json.dumps(metadata, default=str))


def _eventbridge_at_schedule(
    schedule_time: datetime.datetime, schedule_expression_timezone: Optional[str]
) -> Tuple[str, str]:
    """
    EventBridge one-time schedules interpret the clock in ScheduleExpressionTimezone.
    Without that parameter, `at(YYYY-MM-DDTHH:MM:SS)` is UTC, which shifts wall times.
    """
    iana_tz = schedule_expression_timezone or settings.TIME_ZONE
    if django_timezone.is_naive(schedule_time):
        schedule_time = django_timezone.make_aware(
            schedule_time, django_timezone.get_default_timezone()
        )
    local = schedule_time.astimezone(ZoneInfo(iana_tz))
    at_expression = f"at({local.strftime('%Y-%m-%dT%H:%M:%S')})"
    return at_expression, iana_tz


AWS_REGION = common_settings.AWS_REGION
LAMBDA_SEND_SMS_ARN = common_settings.AWS_LAMBDA_SEND_SMS_ARN
LAMBDA_SEND_EMAIL_ARN = common_settings.AWS_LAMBDA_SEND_EMAIL_ARN
SCHEDULER_POLICY_ARN = common_settings.AWS_SCHEDULER_POLICY_ARN

lambda_client = boto3.client("lambda", region_name=AWS_REGION)
events_client = boto3.client("events", region_name=AWS_REGION)
schedule_client = boto3.client("scheduler", region_name=AWS_REGION)

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


@dataclass
class SendResult:
    ok: bool
    error: Optional[str] = None


class EmailService:
    def send(self, subject, to_email, template, context):
        try:
            html_content = render_to_string(template, context)
            text_content = render_to_string(template.replace(".html", ".txt"), context)

            payload = {
                "to_email": to_email,
                "subject": subject,
                "html_content": html_content,
                "text_content": text_content,
                "from_email": settings.DEFAULT_FROM_EMAIL,
            }

            response = lambda_client.invoke(
                FunctionName=LAMBDA_SEND_EMAIL_ARN,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode("utf-8"),
            )

            body_bytes = response["Payload"].read()
            body_str = body_bytes.decode("utf-8")
            result = json.loads(body_str) if body_str else {}

            logger.info(
                "Email sent to %s: %s with result: %s", to_email, subject, result
            )
            return SendResult(ok=True)
        except Exception as exc:
            logger.exception("Email send failed")
            return SendResult(ok=False, error=str(exc))

    def send_async(self, subject, to_email, template, context):
        def _send():
            self.send(subject, to_email, template, context)

        thread = threading.Thread(target=_send)
        thread.start()
        return SendResult(ok=True)

    def send_scheduled(
        self,
        subject,
        to_email,
        template,
        context,
        schedule_time,
        schedule_name,
        schedule_expression_timezone: Optional[str] = None,
    ):
        try:
            at_expression, iana_tz = _eventbridge_at_schedule(
                schedule_time, schedule_expression_timezone
            )
            html_content = render_to_string(template, context)
            text_content = render_to_string(template.replace(".html", ".txt"), context)
            payload = {
                "to_email": to_email,
                "subject": subject,
                "html_content": html_content,
                "text_content": text_content,
                "from_email": settings.DEFAULT_FROM_EMAIL,
            }
            response = schedule_client.create_schedule(
                Name=schedule_name,
                ScheduleExpression=at_expression,
                State="ENABLED",
                FlexibleTimeWindow={
                    "Mode": "OFF",
                },
                Description=f"Email to {to_email} at {schedule_time}",
                Target={
                    "Arn": LAMBDA_SEND_EMAIL_ARN,
                    "RoleArn": SCHEDULER_POLICY_ARN,
                    "Input": json.dumps(payload),
                },
                ScheduleExpressionTimezone=iana_tz,
                GroupName="bookngon-calendar",
            )
            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Email schedule failed")
            return SendResult(ok=False, error=str(exc))

    def destroy_scheduled(self, schedule_name: str) -> SendResult:
        try:
            schedule_client.delete_schedule(
                Name=schedule_name, GroupName="bookngon-calendar"
            )
            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Email destroy scheduled failed")
            return SendResult(ok=False, error=str(exc))


class SMSService:
    group_name: str = "bookngon-calendar"

    def send(
        self,
        to_phone: str,
        body: str,
        business_id: Optional[int] = None,
        business_twilio_phone_number: Optional[str] = None,
    ) -> SendResult:
        try:
            message = f"{body} {common_settings.OPT_OUT_MESSAGE}"
            from_phone_number = common_settings.SMS_DEFAULT_SENDER
            if business_twilio_phone_number:
                from_phone_number = business_twilio_phone_number

            payload = {
                "phone_number": to_phone,
                "message": message,
                "from_phone_number": from_phone_number,
            }

            response = lambda_client.invoke(
                FunctionName=LAMBDA_SEND_SMS_ARN,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode("utf-8"),
            )
            # Body is a StreamingBody; decode to string then JSON
            body_bytes = response["Payload"].read()
            body_str = body_bytes.decode("utf-8")
            result = json.loads(body_str) if body_str else {}
            # Optionally look at FunctionError or LogResult

            if result.get("statusCode", 0) != 200:
                print(f"Failed to send SMS: {result}")
                Notification.objects.create(
                    channel=Notification.Channel.SMS,
                    to=to_phone,
                    body=message,
                    status=Notification.Status.FAILED,
                    business_id=business_id,
                )

                return SendResult(ok=False, error=f"Failed to send SMS: {result}")

            logger.warning(f"========= SMS to {to_phone}: {message}")
            Notification.objects.create(
                channel=Notification.Channel.SMS,
                to=to_phone,
                body=message,
                status=Notification.Status.SENT,
                business_id=business_id,
            )

            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("SMS send failed")
            return SendResult(ok=False, error=str(exc))

    def send_async(
        self,
        to_phone: str,
        body: str,
        business_id: Optional[int] = None,
        business_twilio_phone_number: Optional[str] = None,
    ) -> SendResult:
        def _send():
            self.send(to_phone, body, business_id, business_twilio_phone_number)

        thread = threading.Thread(target=_send)
        thread.start()
        return SendResult(ok=True)

    def send_scheduled(
        self,
        to_phone: str,
        body: str,
        business_id: Optional[int] = None,
        schedule_time: datetime.datetime = None,
        schedule_name: Optional[str] = None,
        business_twilio_phone_number: Optional[str] = None,
        schedule_expression_timezone: Optional[str] = None,
    ) -> SendResult:
        try:

            message = f"{body} {common_settings.OPT_OUT_MESSAGE}"
            at_expression, iana_tz = _eventbridge_at_schedule(
                schedule_time, schedule_expression_timezone
            )
            from_phone_number = common_settings.SMS_DEFAULT_SENDER
            if business_twilio_phone_number:
                from_phone_number = business_twilio_phone_number

            response = schedule_client.create_schedule(
                Name=schedule_name,
                ScheduleExpression=at_expression,
                State="ENABLED",
                FlexibleTimeWindow={
                    "Mode": "OFF",
                },
                Description=f"SMS to {to_phone} at {schedule_time}",
                Target={
                    "Arn": LAMBDA_SEND_SMS_ARN,
                    "RoleArn": SCHEDULER_POLICY_ARN,
                    "Input": json.dumps(
                        {
                            "phone_number": to_phone,
                            "message": message,
                            "from_phone_number": from_phone_number,
                        }
                    ),
                },
                ScheduleExpressionTimezone=iana_tz,
                GroupName=self.group_name,
            )
            Notification.objects.create(
                channel=Notification.Channel.SMS,
                to=to_phone,
                body=message,
                status=Notification.Status.PENDING,
                business_id=business_id,
                data={
                    "schedule_name": schedule_name,
                    "schedule_time": schedule_time.isoformat(),
                },
            )

            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("SMS schedule failed")
            return SendResult(ok=False, error=str(exc))

    def destroy_scheduled(self, schedule_name: str) -> SendResult:
        try:

            schedule_client.delete_schedule(
                Name=schedule_name, GroupName=self.group_name
            )
            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("SMS destroy scheduled failed")
            return SendResult(ok=False, error=str(exc))


class PushService:
    def send_group(
        self, group_name: str, title: str, body: str, data: Optional[Dict] = None
    ) -> SendResult:
        try:
            payload = {"title": title, "body": body}
            response = send_group_notification(
                group_name=group_name, payload=payload, ttl=1000
            )
            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Push send failed")
            return SendResult(ok=False, error=str(exc))

    def send_user(
        self, user: User, title: str, body: str, data: Optional[Dict] = None
    ) -> SendResult:
        try:
            payload = {"title": title, "body": body}
            response = send_user_notification(user=user, payload=payload, ttl=1000)
            return SendResult(ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Push send failed")
            return SendResult(ok=False, error=str(exc))

    def send_client(
        self, client, title: str, body: str, data: Optional[Dict] = None
    ) -> SendResult:
        """Send push notification to a Client via their group."""
        group_name = f"client_{client.id}"
        return self.send_group(group_name, title, body, data)


class NotificationDispatcher:
    def __init__(self) -> None:
        self.sms = SMSService()
        self.push = PushService()
        self.email = EmailService()

    def dispatch(
        self,
        channel: str,
        to: str | Staff,
        title: str,
        body: str,
        business_id: Optional[int] = None,
        data: Optional[Dict] = None,
        group_name: Optional[str] = None,
        business_twilio_phone_number: Optional[str] = None,
    ) -> SendResult:

        if channel == Notification.Channel.SMS:
            return self.sms.send(to, body, business_id, business_twilio_phone_number)
        if channel == Notification.Channel.PUSH:
            
            # Save notification to database for push notifications
            if group_name:
                NotificationService.save_notification(
                    title=title,
                    body=body,
                    channel=Notification.Channel.PUSH,
                    to="business_managers,staff",
                    business_id=business_id,
                    metadata=data,
                )
                return self.push.send_group(group_name, title, body, data)
            
            if isinstance(to, Staff):
                return self.push.send_user(to, title, body, data)
            
               

        if channel == Notification.Channel.EMAIL:
            return self.email.send(
                subject=title,
                to_email=to,
                template="emails/gift_card.html",
                context=data,
            )

        return SendResult(ok=False, error=f"Unsupported channel: {channel}")

    def dispatchAsync(
        self,
        channel: str,
        to: str | Staff,
        title: str,
        body: str,
        business_id: Optional[int] = None,
        data: Optional[Dict] = None,
        group_name: Optional[str] = None,
        business_twilio_phone_number: Optional[str] = None,
    ) -> SendResult:
        def _dispatch():
            result = self.dispatch(
                channel,
                to,
                title,
                body,
                business_id,
                data,
                group_name,
                business_twilio_phone_number,
            )
            return result

        thread = threading.Thread(target=_dispatch)
        thread.start()
        return SendResult(ok=True)

    def dispatch_scheduled(
        self,
        channel: str,
        to: str | Staff,
        title: str,
        body: str,
        business_id: Optional[int] = None,
        data: Optional[Dict] = None,
        schedule_time: Optional[datetime.datetime] = None,
        schedule_name: Optional[str] = None,
        business_twilio_phone_number: Optional[str] = None,
        schedule_expression_timezone: Optional[str] = None,
    ) -> SendResult:
        if channel == Notification.Channel.SMS:
            return self.sms.send_scheduled(
                to,
                body,
                business_id,
                schedule_time,
                schedule_name,
                business_twilio_phone_number,
                schedule_expression_timezone,
            )
        return SendResult(ok=False, error=f"Unsupported channel: {channel}")

    def dispatch_destroy_scheduled(
        self, channel: str, schedule_name: str
    ) -> SendResult:
        if channel == Notification.Channel.SMS:
            return self.sms.destroy_scheduled(schedule_name)
        return SendResult(ok=False, error=f"Unsupported channel: {channel}")

class NotificationService:

    @staticmethod
    def save_notification(
        title: str,
        body: str,
        channel: str = Notification.Channel.PUSH,
        to: str | int | None = None,
        business_id: str | None = None,
        metadata: Optional[Dict] = None,
    ) -> SendResult:
        try:
            to_str = str(to) if to is not None else ""
            Notification.objects.create(
                title=title,
                body=body,
                business_id=business_id,
                to=to_str,
                channel=channel,
                data=json_safe_metadata(metadata),
            )
            return SendResult(ok=True)
        except Exception as e:
            logger.error(f"Error saving notification: {e}")
            return SendResult(ok=False, error=str(e))