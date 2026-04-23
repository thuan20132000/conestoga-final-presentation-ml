from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from faker import Faker
import random

from staff.models import Staff
from business.models import Business
from notifications.models import Notification, PushDevice


class Command(BaseCommand):
    help = "Create sample notifications and push devices for existing businesses and staff"

    def add_arguments(self, parser):
        parser.add_argument("--per_business", type=int, default=5, help="Number of notifications per business")
        parser.add_argument("--push_devices_per_business", type=int, default=3, help="Number of push devices per business")

    def handle(self, *args, **options):
        fake = Faker()
        per_business = options["per_business"]
        devices_per_business = options["push_devices_per_business"]

        businesses = Business.objects.all()
        if not businesses.exists():
            self.stdout.write(self.style.WARNING("No businesses found. Create businesses first."))
            return

        created_notifications = 0
        created_devices = 0

        with transaction.atomic():
            for business in businesses:
                staff_qs = Staff.objects.filter(business=business)
                staff_for_business = list(staff_qs)

                # Push devices
                for _ in range(devices_per_business):
                    user = random.choice(staff_for_business) if staff_for_business else None
                    token = f"sample-token-{business.id}-{fake.uuid4()}"
                    PushDevice.objects.get_or_create(
                        token=token,
                        defaults={
                            "user": user,
                            "business": business,
                            "provider": random.choice(["fcm", "apns"]),
                            "active": True,
                        },
                    )
                    created_devices += 1

                # Notifications
                for _ in range(per_business):
                    channel = random.choice([Notification.Channel.EMAIL, Notification.Channel.SMS, Notification.Channel.PUSH])
                    user = random.choice(staff_for_business) if staff_for_business else None

                    if channel == Notification.Channel.EMAIL:
                        to = user.email if user and user.email else fake.email()
                        title = fake.sentence(nb_words=6)
                        body = fake.paragraph(nb_sentences=3)
                    elif channel == Notification.Channel.SMS:
                        to = user.phone if user and user.phone else fake.msisdn()
                        title = ""
                        body = fake.sentence(nb_words=10)
                    else:
                        # push: use an existing device if possible, else random token
                        device = PushDevice.objects.filter(business=business, active=True).first()
                        to = device.token if device else f"sample-token-{business.id}-{fake.uuid4()}"
                        title = fake.sentence(nb_words=5)
                        body = fake.sentence(nb_words=12)

                    Notification.objects.create(
                        user=user,
                        business=business,
                        channel=channel,
                        to=to,
                        title=title,
                        body=body,
                        data={"sample": True, "business_id": business.id},
                        status=Notification.Status.PENDING,
                        created_at=timezone.now(),
                    )
                    created_notifications += 1

        self.stdout.write(self.style.SUCCESS(
            f"Created {created_notifications} notifications and {created_devices} push devices across {businesses.count()} businesses."
        ))
