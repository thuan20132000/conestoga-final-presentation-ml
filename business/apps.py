from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BusinessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "business"
    verbose_name = _("Business Management")
    
    def ready(self):
        import business.signals