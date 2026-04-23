from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='service.Service')
def add_service_to_all_staff(sender, instance, created, **kwargs):
    if not created:
        return

    from staff.models import Staff, StaffService
    business_staff = Staff.objects.filter(business=instance.business, is_active=True)
    StaffService.objects.bulk_create(
        [StaffService(staff=staff, service=instance) for staff in business_staff],
        ignore_conflicts=True,
    )